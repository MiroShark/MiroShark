"""Graph memory update service that processes agent activities and updates Neo4j."""

import time
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from queue import Queue, Empty

from ..utils.logger import get_logger
from ..storage import GraphStorage

logger = get_logger('miroshark.graph_memory_updater')


@dataclass
class AgentActivity:
    """Agent activity record"""
    platform: str           # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str        # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any]
    round_num: int
    timestamp: str

    def to_episode_text(self) -> str:
        """
        Convert activity to natural language text description

        Use natural language description format so NER extractor can extract entities and relationships
        """
        action_descriptions = {
            "CREATE_POST": self._describe_create_post,
            "LIKE_POST": self._describe_like_post,
            "DISLIKE_POST": self._describe_dislike_post,
            "REPOST": self._describe_repost,
            "QUOTE_POST": self._describe_quote_post,
            "FOLLOW": self._describe_follow,
            "CREATE_COMMENT": self._describe_create_comment,
            "LIKE_COMMENT": self._describe_like_comment,
            "DISLIKE_COMMENT": self._describe_dislike_comment,
            "SEARCH_POSTS": self._describe_search,
            "SEARCH_USER": self._describe_search_user,
            "MUTE": self._describe_mute,
        }

        describe_func = action_descriptions.get(self.action_type, self._describe_generic)
        description = describe_func()

        return f"{self.agent_name}: {description}"

    def _describe_create_post(self) -> str:
        content = self.action_args.get("content", "")
        if content:
            return f"Posted a post: \"{content}\""
        return "Posted a post"

    def _describe_like_post(self) -> str:
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        if post_content and post_author:
            return f"Liked {post_author}'s post: \"{post_content}\""
        elif post_content:
            return f"Liked a post: \"{post_content}\""
        elif post_author:
            return f"Liked a post by {post_author}"
        return "Liked a post"

    def _describe_dislike_post(self) -> str:
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        if post_content and post_author:
            return f"Disliked {post_author}'s post: \"{post_content}\""
        elif post_content:
            return f"Disliked a post: \"{post_content}\""
        elif post_author:
            return f"Disliked a post by {post_author}"
        return "Disliked a post"

    def _describe_repost(self) -> str:
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        if original_content and original_author:
            return f"Reposted {original_author}'s post: \"{original_content}\""
        elif original_content:
            return f"Reposted a post: \"{original_content}\""
        elif original_author:
            return f"Reposted a post by {original_author}"
        return "Reposted a post"

    def _describe_quote_post(self) -> str:
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        quote_content = self.action_args.get("quote_content", "") or self.action_args.get("content", "")
        base = ""
        if original_content and original_author:
            base = f"Quoted {original_author}'s post \"{original_content}\""
        elif original_content:
            base = f"Quoted a post \"{original_content}\""
        elif original_author:
            base = f"Quoted a post by {original_author}"
        else:
            base = "Quoted a post"
        if quote_content:
            base += f", commented: \"{quote_content}\""
        return base

    def _describe_follow(self) -> str:
        target_user_name = self.action_args.get("target_user_name", "")
        if target_user_name:
            return f"Followed user \"{target_user_name}\""
        return "Followed a user"

    def _describe_create_comment(self) -> str:
        content = self.action_args.get("content", "")
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        if content:
            if post_content and post_author:
                return f"Commented on {post_author}'s post \"{post_content}\": \"{content}\""
            elif post_content:
                return f"Commented on post \"{post_content}\": \"{content}\""
            elif post_author:
                return f"Commented on {post_author}'s post: \"{content}\""
            return f"Commented: \"{content}\""
        return "Left a comment"

    def _describe_like_comment(self) -> str:
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        if comment_content and comment_author:
            return f"Liked {comment_author}'s comment: \"{comment_content}\""
        elif comment_content:
            return f"Liked a comment: \"{comment_content}\""
        elif comment_author:
            return f"Liked a comment by {comment_author}"
        return "Liked a comment"

    def _describe_dislike_comment(self) -> str:
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        if comment_content and comment_author:
            return f"Disliked {comment_author}'s comment: \"{comment_content}\""
        elif comment_content:
            return f"Disliked a comment: \"{comment_content}\""
        elif comment_author:
            return f"Disliked a comment by {comment_author}"
        return "Disliked a comment"

    def _describe_search(self) -> str:
        query = self.action_args.get("query", "") or self.action_args.get("keyword", "")
        return f"Searched for \"{query}\""if query else "Performed a search"

    def _describe_search_user(self) -> str:
        query = self.action_args.get("query", "") or self.action_args.get("username", "")
        return f"Searched for user \"{query}\""if query else "Searched for user"

    def _describe_mute(self) -> str:
        target_user_name = self.action_args.get("target_user_name", "")
        if target_user_name:
            return f"Muted user \"{target_user_name}\""
        return "Muted a user"

    def _describe_generic(self) -> str:
        return f"Executed {self.action_type} action"


class GraphMemoryUpdater:
    """
    Graph memory update service (via GraphStorage / Neo4j)

    Monitors simulation action logs and sends agent activities to the graph in real-time.
    Batches activities by platform, accumulating BATCH_SIZE activities before sending each batch.
    """

    BATCH_SIZE = 5

    PLATFORM_DISPLAY_NAMES = {
        'twitter': 'worldinterface1',
        'reddit': 'worldinterface2',
    }

    SEND_INTERVAL = 0.5
    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self, graph_id: str, storage: GraphStorage):
        """
        InitializeUpdatedevice

        Args:
            graph_id: GraphID
            storage: GraphStorage instance (injected)
        """
        self.graph_id = graph_id
        self.storage = storage

        self._activity_queue: Queue = Queue()

        self._platform_buffers: Dict[str, List[AgentActivity]] = {
            'twitter': [],
            'reddit': [],
        }
        self._buffer_lock = threading.Lock()

        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

        self._total_activities = 0
        self._total_sent = 0
        self._total_items_sent = 0
        self._failed_count = 0
        self._skipped_count = 0

        logger.info(f"GraphMemoryUpdater initialized: graph_id={graph_id}, batch_size={self.BATCH_SIZE}")

    def _get_platform_display_name(self, platform: str) -> str:
        return self.PLATFORM_DISPLAY_NAMES.get(platform.lower(), platform)

    def start(self):
        """Start background worker thread"""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name=f"GraphMemoryUpdater-{self.graph_id[:8]}"
        )
        self._worker_thread.start()
        logger.info(f"GraphMemoryUpdater started: graph_id={self.graph_id}")

    def stop(self):
        """Stop background worker thread"""
        self._running = False

        self._flush_remaining()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)

        logger.info(f"GraphMemoryUpdater stopped: graph_id={self.graph_id}, "
                     f"total_activities={self._total_activities}, "
                     f"batches_sent={self._total_sent}, "
                     f"items_sent={self._total_items_sent}, "
                     f"failed={self._failed_count}, "
                     f"skipped={self._skipped_count}")

    def add_activity(self, activity: AgentActivity):
        """Add an agent activity to queue"""
        if activity.action_type == "DO_NOTHING":
            self._skipped_count += 1
            return

        self._activity_queue.put(activity)
        self._total_activities += 1
        logger.debug(f"Add activity to queue: {activity.agent_name} - {activity.action_type}")

    def add_activity_from_dict(self, data: Dict[str, Any], platform: str):
        """Add activity from dict data"""
        if "event_type" in data:
            return

        activity = AgentActivity(
            platform=platform,
            agent_id=data.get("agent_id", 0),
            agent_name=data.get("agent_name", ""),
            action_type=data.get("action_type", ""),
            action_args=data.get("action_args", {}),
            round_num=data.get("round", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )

        self.add_activity(activity)

    def _worker_loop(self):
        """Background worker loop - batch send activities to graph by platform"""
        while self._running or not self._activity_queue.empty():
            try:
                try:
                    activity = self._activity_queue.get(timeout=1)

                    platform = activity.platform.lower()
                    with self._buffer_lock:
                        if platform not in self._platform_buffers:
                            self._platform_buffers[platform] = []
                        self._platform_buffers[platform].append(activity)

                        if len(self._platform_buffers[platform]) >= self.BATCH_SIZE:
                            batch = self._platform_buffers[platform][:self.BATCH_SIZE]
                            self._platform_buffers[platform] = self._platform_buffers[platform][self.BATCH_SIZE:]
                            self._send_batch_activities(batch, platform)
                            time.sleep(self.SEND_INTERVAL)

                except Empty:
                    pass

            except Exception as e:
                logger.error(f"Worker loop exception: {e}")
                time.sleep(1)

    def _send_batch_activities(self, activities: List[AgentActivity], platform: str):
        """
        Send batched activities to the graph by merging them as text and using add_text to trigger NER.

        Batch-level metadata:
          - kind: "belief" if the batch is entirely expressive actions
            (CREATE_POST / QUOTE_POST); otherwise "observation".
          - source_type: always "agent" (these originated from sim agents).
          - source_id: platform + round, so edges are traceable back to the
            simulation round that produced them.
          - valid_at: earliest timestamp in the batch.
        """
        if not activities:
            return

        episode_texts = [activity.to_episode_text() for activity in activities]
        combined_text = "\n".join(episode_texts)

        # Determine epistemic kind at the batch level.
        expressive_actions = {"CREATE_POST", "QUOTE_POST", "CREATE_COMMENT"}
        edge_kind = (
            "belief"
            if all(a.action_type in expressive_actions for a in activities)
            else "observation"
        )

        # Source id: platform + round (when homogeneous) keeps edges queryable
        # per-simulation-round. Mixed batches fall back to platform only.
        rounds = {a.round_num for a in activities}
        source_id = (
            f"{platform}:round_{next(iter(rounds))}"
            if len(rounds) == 1
            else f"{platform}:mixed"
        )

        valid_at = min(a.timestamp for a in activities)

        for attempt in range(self.MAX_RETRIES):
            try:
                self.storage.add_text(
                    self.graph_id,
                    combined_text,
                    valid_at=valid_at,
                    kind=edge_kind,
                    source_type="agent",
                    source_id=source_id,
                )

                self._total_sent += 1
                self._total_items_sent += len(activities)
                display_name = self._get_platform_display_name(platform)
                logger.info(
                    f"Successfully batch sent {len(activities)} {display_name} activities "
                    f"to graph {self.graph_id} (kind={edge_kind}, source_id={source_id})"
                )
                logger.debug(f"Batch preview: {combined_text[:200]}...")
                return

            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"Batch send to graph failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"Batch send to graph failed after {self.MAX_RETRIES} retries: {e}")
                    self._failed_count += 1

    def _flush_remaining(self):
        """Send remaining activities in queue and buffers"""
        while not self._activity_queue.empty():
            try:
                activity = self._activity_queue.get_nowait()
                platform = activity.platform.lower()
                with self._buffer_lock:
                    if platform not in self._platform_buffers:
                        self._platform_buffers[platform] = []
                    self._platform_buffers[platform].append(activity)
            except Empty:
                break

        with self._buffer_lock:
            for platform, buffer in self._platform_buffers.items():
                if buffer:
                    display_name = self._get_platform_display_name(platform)
                    logger.info(f"Send remaining {len(buffer)} {display_name} platform activities")
                    self._send_batch_activities(buffer, platform)
            for platform in self._platform_buffers:
                self._platform_buffers[platform] = []

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics"""
        with self._buffer_lock:
            buffer_sizes = {p: len(b) for p, b in self._platform_buffers.items()}

        return {
            "graph_id": self.graph_id,
            "batch_size": self.BATCH_SIZE,
            "total_activities": self._total_activities,
            "batches_sent": self._total_sent,
            "items_sent": self._total_items_sent,
            "failed_count": self._failed_count,
            "skipped_count": self._skipped_count,
            "queue_size": self._activity_queue.qsize(),
            "buffer_sizes": buffer_sizes,
            "running": self._running,
        }


class GraphMemoryManager:
    """
    Manages graph memory updaters for multiple simulations.

    Each simulation can have its own independent updater instance.
    NOTE: create_updater() requires a GraphStorage instance — must be passed in.
    """

    _updaters: Dict[str, GraphMemoryUpdater] = {}
    _lock = threading.Lock()

    @classmethod
    def create_updater(
        cls, simulation_id: str, graph_id: str, storage: GraphStorage
    ) -> GraphMemoryUpdater:
        """
        Create a graph memory updater for a simulation.

        Args:
            simulation_id: Simulation ID
            graph_id: Graph ID
            storage: GraphStorage instance
        """
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()

            updater = GraphMemoryUpdater(graph_id, storage)
            updater.start()
            cls._updaters[simulation_id] = updater

            logger.info(f"Create graph memory updater: simulation_id={simulation_id}, graph_id={graph_id}")
            return updater

    @classmethod
    def get_updater(cls, simulation_id: str) -> Optional[GraphMemoryUpdater]:
        """Get updater for simulation"""
        return cls._updaters.get(simulation_id)

    @classmethod
    def stop_updater(cls, simulation_id: str):
        """Stop and remove updater for simulation"""
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
                del cls._updaters[simulation_id]
                logger.info(f"Stopped graph memory updater: simulation_id={simulation_id}")

    _stop_all_done = False

    @classmethod
    def stop_all(cls):
        """Stop all updaters"""
        if cls._stop_all_done:
            return
        cls._stop_all_done = True

        with cls._lock:
            if cls._updaters:
                for simulation_id, updater in list(cls._updaters.items()):
                    try:
                        updater.stop()
                    except Exception as e:
                        logger.error(f"Failed to stop updater: simulation_id={simulation_id}, error={e}")
                cls._updaters.clear()
            logger.info("Stopped all graph memory updaters")
