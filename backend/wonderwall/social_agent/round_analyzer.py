"""
Round Analyzer — aggregates per-round metrics and generates feedback for agents.

After each simulation round, the analyzer:
1. Queries the SQLite trace/post tables for that round's actions
2. Computes belief updates for each agent
3. Generates per-agent feedback text (engagement on own posts, community shift)
4. Generates a world-state summary (sentiment distribution, viral content)
5. Accumulates snapshots into a SimulationTrajectory for the report agent

This runs in the simulation scripts, NOT inside Wonderwall's WonderwallEnv,
keeping the upstream framework untouched.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from wonderwall.social_agent.belief_state import BeliefState


@dataclass
class RoundSnapshot:
    """Captured state after one simulation round."""

    round_num: int
    timestamp: str = ""
    total_posts_created: int = 0
    total_engagements: int = 0
    active_agent_count: int = 0
    belief_positions: Dict[int, Dict[str, float]] = field(default_factory=dict)
    belief_deltas: Dict[int, Dict[str, float]] = field(default_factory=dict)
    viral_posts: List[Dict[str, Any]] = field(default_factory=list)
    sentiment_summary: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "timestamp": self.timestamp,
            "total_posts_created": self.total_posts_created,
            "total_engagements": self.total_engagements,
            "active_agent_count": self.active_agent_count,
            "belief_positions": {
                str(k): v for k, v in self.belief_positions.items()
            },
            "belief_deltas": {
                str(k): v for k, v in self.belief_deltas.items()
            },
            "viral_posts": self.viral_posts,
            "sentiment_summary": self.sentiment_summary,
        }


class SimulationTrajectory:
    """Accumulates round snapshots for the entire simulation."""

    def __init__(self):
        self.snapshots: List[RoundSnapshot] = []
        self.topics: List[str] = []

    def add_snapshot(self, snapshot: RoundSnapshot):
        self.snapshots.append(snapshot)

    def save(self, path: str):
        """Save trajectory to JSON for the report agent."""
        data = {
            "topics": self.topics,
            "total_rounds": len(self.snapshots),
            "snapshots": [s.to_dict() for s in self.snapshots],
            "belief_trajectories": self._compute_trajectories(),
            "opinion_convergence": self._compute_convergence(),
            "turning_points": self._find_turning_points(),
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _compute_trajectories(self) -> Dict[str, List[Dict[str, float]]]:
        """Per-topic belief trajectory across all rounds."""
        trajectories: Dict[str, List[Dict[str, float]]] = {}
        for topic in self.topics:
            trajectory = []
            for snap in self.snapshots:
                positions = [
                    pos.get(topic, 0.0)
                    for pos in snap.belief_positions.values()
                    if topic in pos
                ]
                if positions:
                    trajectory.append({
                        "round": snap.round_num,
                        "mean": sum(positions) / len(positions),
                        "min": min(positions),
                        "max": max(positions),
                        "spread": max(positions) - min(positions),
                        "count": len(positions),
                    })
            trajectories[topic] = trajectory
        return trajectories

    def _compute_convergence(self) -> Dict[str, float]:
        """Measure how much opinions converged or diverged per topic."""
        convergence: Dict[str, float] = {}
        for topic in self.topics:
            if len(self.snapshots) < 2:
                convergence[topic] = 0.0
                continue

            first_snap = self.snapshots[0]
            last_snap = self.snapshots[-1]

            first_positions = [
                p.get(topic, 0.0)
                for p in first_snap.belief_positions.values()
                if topic in p
            ]
            last_positions = [
                p.get(topic, 0.0)
                for p in last_snap.belief_positions.values()
                if topic in p
            ]

            if first_positions and last_positions:
                first_spread = max(first_positions) - min(first_positions)
                last_spread = max(last_positions) - min(last_positions)
                # Positive = convergence, negative = polarization
                convergence[topic] = first_spread - last_spread
            else:
                convergence[topic] = 0.0

        return convergence

    def _find_turning_points(self) -> List[Dict[str, Any]]:
        """Find rounds where significant belief shifts occurred."""
        turning_points = []
        for i, snap in enumerate(self.snapshots):
            for agent_id, deltas in snap.belief_deltas.items():
                for topic, delta in deltas.items():
                    if abs(delta) > 0.15:  # Significant shift threshold
                        turning_points.append({
                            "round": snap.round_num,
                            "agent_id": agent_id,
                            "topic": topic,
                            "delta": round(delta, 3),
                            "direction": "toward support" if delta > 0 else "toward opposition",
                        })
        # Return top 20 most significant
        turning_points.sort(key=lambda x: abs(x["delta"]), reverse=True)
        return turning_points[:20]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topics": self.topics,
            "total_rounds": len(self.snapshots),
            "snapshots": [s.to_dict() for s in self.snapshots],
            "belief_trajectories": self._compute_trajectories(),
            "opinion_convergence": self._compute_convergence(),
            "turning_points": self._find_turning_points(),
        }


class RoundAnalyzer:
    """Analyzes a simulation round and produces belief updates + feedback."""

    def __init__(self, topics: List[str]):
        self.topics = topics

    def analyze_round(
        self,
        db_path: str,
        belief_states: Dict[int, BeliefState],
        active_agent_ids: List[int],
        round_num: int,
        actual_actions: Optional[List[Dict[str, Any]]] = None,
    ) -> RoundSnapshot:
        """Analyze one round's actions and update agent beliefs.

        Args:
            db_path: Path to the platform's SQLite database.
            belief_states: Mutable dict of agent_id → BeliefState.
            active_agent_ids: Agent IDs that were active this round.
            round_num: Current round number.
            actual_actions: If available, the list of action dicts from this
                round (used as fallback for building posts_seen when the rec
                table is empty).

        Returns:
            RoundSnapshot with all metrics for this round.
        """
        snapshot = RoundSnapshot(
            round_num=round_num,
            timestamp=datetime.now().isoformat(),
            active_agent_count=len(active_agent_ids),
        )

        follow_graph: Dict[int, set] = {}  # follower_id -> set of followee_ids

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent read/write
            conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes (safe with WAL)
            cursor = conn.cursor()

            # Get posts created this round (approximate: last N rows)
            posts_this_round = self._get_recent_posts(cursor, len(active_agent_ids) * 2)
            snapshot.total_posts_created = len(posts_this_round)

            # Get engagement data
            engagement_by_agent = self._get_engagement_by_agent(cursor, active_agent_ids)
            snapshot.total_engagements = sum(
                e.get("likes_received", 0) + e.get("dislikes_received", 0)
                for e in engagement_by_agent.values()
            )

            # Get posts each agent saw (from rec table)
            posts_seen_by_agent = self._get_posts_seen_by_agent(cursor, active_agent_ids)

            # Load social graph for fallback post distribution
            follow_graph = self._get_follow_graph(cursor, active_agent_ids)

            # Get top viral posts
            snapshot.viral_posts = self._get_viral_posts(cursor, limit=3)

            conn.close()
        except Exception:
            conn = None
            posts_seen_by_agent = {}
            engagement_by_agent = {}

        # Fallback: if the rec table yielded few posts for most agents,
        # build posts_seen from the round's actual_actions instead.
        agents_with_posts = sum(
            1 for aid in active_agent_ids
            if posts_seen_by_agent.get(aid)
        )
        rec_coverage = agents_with_posts / max(len(active_agent_ids), 1)
        if rec_coverage < 0.5 and actual_actions:
            action_posts = self._build_posts_seen_from_actions(
                actual_actions, active_agent_ids, follow_graph
            )
            # Merge: for agents who got nothing from rec, use action-derived data
            for aid in active_agent_ids:
                if not posts_seen_by_agent.get(aid) and action_posts.get(aid):
                    posts_seen_by_agent[aid] = action_posts[aid]

        # Update beliefs for each active agent
        for agent_id in active_agent_ids:
            if agent_id not in belief_states:
                continue

            bs = belief_states[agent_id]
            posts_seen = posts_seen_by_agent.get(agent_id, [])
            own_engagement = engagement_by_agent.get(agent_id, {})

            deltas = bs.update_from_round(posts_seen, own_engagement, round_num)

            snapshot.belief_positions[agent_id] = dict(bs.positions)
            if deltas:
                snapshot.belief_deltas[agent_id] = deltas

        # Compute aggregate sentiment
        for topic in self.topics:
            all_positions = [
                bs.positions.get(topic, 0.0)
                for bs in belief_states.values()
                if topic in bs.positions
            ]
            if all_positions:
                snapshot.sentiment_summary[topic] = round(
                    sum(all_positions) / len(all_positions), 3
                )

        return snapshot

    def generate_agent_feedback(
        self,
        snapshot: RoundSnapshot,
        agent_id: int,
        belief_state: Optional[BeliefState] = None,
    ) -> str:
        """Generate per-agent feedback text for the next round's prompt.

        Returns empty string if there's nothing meaningful to report.
        """
        lines = []

        # Engagement on own posts
        # (We approximate from the snapshot — exact per-agent engagement
        #  would need the trace table, which we already queried above)
        deltas = snapshot.belief_deltas.get(agent_id, {})
        if deltas:
            for topic, delta in deltas.items():
                if abs(delta) > 0.05:
                    direction = "more supportive" if delta > 0 else "more skeptical"
                    lines.append(
                        f"After reading others' perspectives on {topic}, "
                        f"you've become slightly {direction}."
                    )

        # World state summary
        if snapshot.viral_posts:
            top = snapshot.viral_posts[0]
            lines.append(
                f"The most discussed post this round: "
                f"\"{top.get('content', '')[:100]}\" "
                f"({top.get('num_likes', 0)} likes)"
            )

        # Sentiment shift
        for topic, avg in snapshot.sentiment_summary.items():
            label = "supportive" if avg > 0.1 else "opposed" if avg < -0.1 else "divided"
            lines.append(f"Community sentiment on {topic}: generally {label} (avg: {avg:.2f})")

        if not lines:
            return ""

        return "[Round Update]\n" + "\n".join(lines)

    # ── SQLite queries (batched for performance) ──────────────────

    def _get_recent_posts(self, cursor, limit: int) -> List[Dict[str, Any]]:
        try:
            cursor.execute(
                "SELECT post_id, user_id, content, num_likes, num_dislikes "
                "FROM post ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def _get_engagement_by_agent(
        self, cursor, agent_ids: List[int]
    ) -> Dict[int, Dict[str, int]]:
        """Get likes/dislikes received by each agent's posts — single batched query."""
        if not agent_ids:
            return {}
        result = {}
        try:
            placeholders = ",".join("?" * len(agent_ids))
            cursor.execute(
                f"SELECT user_id, COALESCE(SUM(num_likes), 0) as likes, "
                f"COALESCE(SUM(num_dislikes), 0) as dislikes "
                f"FROM post WHERE user_id IN ({placeholders}) "
                f"GROUP BY user_id",
                agent_ids,
            )
            for row in cursor.fetchall():
                result[row["user_id"]] = {
                    "likes_received": row["likes"],
                    "dislikes_received": row["dislikes"],
                }
        except Exception:
            pass
        return result

    def _get_posts_seen_by_agent(
        self, cursor, agent_ids: List[int]
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Get posts recommended to all active agents — single batched query."""
        if not agent_ids:
            return {}
        result: Dict[int, List[Dict[str, Any]]] = {aid: [] for aid in agent_ids}
        try:
            placeholders = ",".join("?" * len(agent_ids))
            cursor.execute(
                f"SELECT r.user_id, p.content, p.user_id as author_id, "
                f"p.num_likes, p.num_dislikes "
                f"FROM rec r JOIN post p ON r.post_id = p.post_id "
                f"WHERE r.user_id IN ({placeholders})",
                agent_ids,
            )
            for row in cursor.fetchall():
                uid = row["user_id"]
                if uid in result:
                    result[uid].append(dict(row))
        except Exception:
            pass
        return result

    def _get_follow_graph(
        self, cursor, agent_ids: List[int]
    ) -> Dict[int, set[int]]:
        """Load the follow graph for active agents (follower -> set of followees)."""
        graph: Dict[int, set[int]] = {aid: set() for aid in agent_ids}
        if not agent_ids:
            return graph
        try:
            placeholders = ",".join("?" * len(agent_ids))
            cursor.execute(
                f"SELECT follower_id, followee_id FROM follow "
                f"WHERE follower_id IN ({placeholders})",
                agent_ids,
            )
            for row in cursor.fetchall():
                fid = row["follower_id"]
                if fid in graph:
                    graph[fid].add(row["followee_id"])
        except Exception:
            pass
        return graph

    def _build_posts_seen_from_actions(
        self,
        actual_actions: List[Dict[str, Any]],
        active_agent_ids: List[int],
        follow_graph: Dict[int, set[int]],
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Build posts_seen per agent from the round's actual actions.

        An agent "sees" a post if:
        1. The post was created by someone they follow, OR
        2. The post received engagement (likes/comments) this round (popular), OR
        3. The agent directly interacted with it (liked, commented on, etc.)

        This provides a fallback when the rec table is empty.
        """
        result: Dict[int, List[Dict[str, Any]]] = {aid: [] for aid in active_agent_ids}

        # Collect all posts created this round (from CREATE_POST actions)
        round_posts: Dict[int, Dict[str, Any]] = {}  # keyed by agent_id (author)
        # Track which posts got engagement this round
        engaged_posts: Dict[int, int] = {}  # post_author_id -> engagement count
        # Track which agent interacted with which author's content
        agent_interactions: Dict[int, set] = {aid: set() for aid in active_agent_ids}

        for action in actual_actions:
            agent_id = action.get("agent_id")
            action_type = action.get("action_type", "")
            args = action.get("action_args", {})

            if action_type == "CREATE_POST":
                content = args.get("content", "")
                if content and agent_id is not None:
                    round_posts[agent_id] = {
                        "content": content,
                        "author_id": agent_id,
                        "num_likes": 0,
                        "num_dislikes": 0,
                    }
            elif action_type == "CREATE_COMMENT":
                content = args.get("content", "")
                post_author = args.get("post_author_id")
                if content and agent_id is not None:
                    # The comment itself acts as a mini-post others can see
                    if agent_id not in round_posts:
                        round_posts[agent_id] = {
                            "content": content,
                            "author_id": agent_id,
                            "num_likes": 0,
                            "num_dislikes": 0,
                        }
                    # Track engagement on the parent post's author
                    if post_author is not None:
                        try:
                            post_author = int(post_author)
                            engaged_posts[post_author] = engaged_posts.get(post_author, 0) + 1
                            if agent_id in agent_interactions:
                                agent_interactions[agent_id].add(post_author)
                        except (ValueError, TypeError):
                            pass
            elif action_type in ("LIKE_POST", "DISLIKE_POST"):
                post_author = args.get("post_author_id")
                post_content = args.get("post_content", "")
                if post_author is not None:
                    try:
                        post_author = int(post_author)
                        engaged_posts[post_author] = engaged_posts.get(post_author, 0) + 1
                        if agent_id in agent_interactions:
                            agent_interactions[agent_id].add(post_author)
                        # If we have the post content from enrichment, record it
                        if post_content and post_author not in round_posts:
                            round_posts[post_author] = {
                                "content": post_content,
                                "author_id": post_author,
                                "num_likes": 1 if action_type == "LIKE_POST" else 0,
                                "num_dislikes": 1 if action_type == "DISLIKE_POST" else 0,
                            }
                    except (ValueError, TypeError):
                        pass
            elif action_type in ("REPOST", "QUOTE_POST"):
                content = args.get("content", "")
                if content and agent_id is not None and agent_id not in round_posts:
                    round_posts[agent_id] = {
                        "content": content,
                        "author_id": agent_id,
                        "num_likes": 0,
                        "num_dislikes": 0,
                    }

        # Identify "popular" authors (those whose content got engagement)
        popular_threshold = 1  # At least 1 engagement action
        popular_authors = {
            author_id
            for author_id, count in engaged_posts.items()
            if count >= popular_threshold and author_id in round_posts
        }

        # Distribute posts to agents
        for agent_id in active_agent_ids:
            seen: List[Dict] = []
            following = follow_graph.get(agent_id, set())

            for author_id, post_data in round_posts.items():
                if author_id == agent_id:
                    continue  # Skip own posts

                should_see = (
                    author_id in following  # follows the author
                    or author_id in popular_authors  # post was popular
                    or author_id in agent_interactions.get(agent_id, set())  # interacted with
                )

                if should_see:
                    seen.append(post_data)

            # If an agent still sees nothing, show them a sample of round posts
            # (simulates browsing / discovery feed)
            if not seen and round_posts:
                other_posts = [
                    p for aid, p in round_posts.items() if aid != agent_id
                ]
                # Show up to 3 random posts as "discovery"
                sample_size = min(3, len(other_posts))
                if sample_size > 0:
                    import random as _rand
                    seen = _rand.sample(other_posts, sample_size)

            result[agent_id] = seen

        return result

    def _get_viral_posts(self, cursor, limit: int = 3) -> List[Dict[str, Any]]:
        try:
            cursor.execute(
                "SELECT post_id, user_id, content, num_likes, num_dislikes "
                "FROM post ORDER BY num_likes DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []


def update_trust_from_actions(
    belief_states: Dict[int, BeliefState],
    actions: List[Dict[str, Any]],
) -> None:
    """Update agent trust based on round actions.

    Args:
        belief_states: Dict of agent_id → BeliefState.
        actions: List of action dicts with keys: agent_id, action_type, action_args.
    """
    trust_actions = {
        "LIKE_POST": "like",
        "DISLIKE_POST": "dislike",
        "FOLLOW": "follow",
        "UNFOLLOW": "unfollow",
        "MUTE": "mute",
        "LIKE_COMMENT": "like",
        "DISLIKE_COMMENT": "dislike",
    }

    for action in actions:
        agent_id = action.get("agent_id")
        action_type = action.get("action_type", "")
        args = action.get("action_args", {})

        trust_action = trust_actions.get(action_type)
        if not trust_action or agent_id not in belief_states:
            continue

        # Determine the target agent
        target_id = (
            args.get("post_author_id")
            or args.get("followee_id")
            or args.get("target_user_id")
            or args.get("comment_author_id")
        )

        if target_id is not None:
            try:
                target_id = int(target_id)
                belief_states[agent_id].update_trust(target_id, trust_action)
            except (ValueError, TypeError):
                pass
