"""
Wonderwall Simulation Manager
Manages parallel simulation across Twitter and Reddit platforms
Uses preset scripts + LLM-powered configuration parameter generation
"""

import os
import json
import shutil
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..utils.logger import get_logger
from ..utils.trace_context import TraceContext
from ..utils.validation import validate_simulation_id
from .entity_reader import EntityReader
from .wonderwall_profile_generator import WonderwallProfileGenerator
from .simulation_config_generator import SimulationConfigGenerator

logger = get_logger('miroshark.simulation')


class SimulationStatus(str, Enum):
    """Simulation status"""
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"      # Simulation manually stopped
    COMPLETED = "completed"  # Simulation completed naturally
    FAILED = "failed"


# NOTE: Platform membership for a simulation is expressed on SimulationState
# via the ``enable_twitter`` / ``enable_reddit`` / ``enable_polymarket`` flags
# and via plain string fields (e.g. ``twitter_status``). The run scripts use
# ``wonderwall.DefaultPlatformType`` when handing off to the Wonderwall framework.
# A previous local ``PlatformType`` enum here was dead code and has been
# removed — re-add only when MiroShark-side code actually needs an enum.


@dataclass
class SimulationState:
    """Simulation state"""
    simulation_id: str
    project_id: str
    graph_id: str

    # Platform enable status
    enable_twitter: bool = True
    enable_reddit: bool = True
    enable_polymarket: bool = False

    # Number of prediction markets to generate when Polymarket is enabled.
    # Defaults to 1 (historical behavior). Range [1, 5] enforced upstream.
    polymarket_market_count: int = 1

    # Status
    status: SimulationStatus = SimulationStatus.CREATED

    # Preparation phase data
    entities_count: int = 0
    profiles_count: int = 0
    entity_types: List[str] = field(default_factory=list)

    # Config generation info
    config_generated: bool = False
    config_reasoning: str = ""

    # Runtime data
    current_round: int = 0
    twitter_status: str = "not_started"
    reddit_status: str = "not_started"

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Error info
    error: Optional[str] = None

    # Fork lineage
    parent_simulation_id: Optional[str] = None
    config_diff: Optional[Dict] = None

    # Public-embed visibility. Embed endpoints require this to be True; otherwise
    # they 403. Defaults to False so existing simulations remain private until
    # their owner explicitly publishes.
    is_public: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Full state dictionary (for internal use)"""
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "enable_twitter": self.enable_twitter,
            "enable_reddit": self.enable_reddit,
            "enable_polymarket": self.enable_polymarket,
            "polymarket_market_count": self.polymarket_market_count,
            "status": self.status.value,
            "entities_count": self.entities_count,
            "profiles_count": self.profiles_count,
            "entity_types": self.entity_types,
            "config_generated": self.config_generated,
            "config_reasoning": self.config_reasoning,
            "current_round": self.current_round,
            "twitter_status": self.twitter_status,
            "reddit_status": self.reddit_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
            "parent_simulation_id": self.parent_simulation_id,
            "config_diff": self.config_diff,
            "is_public": self.is_public,
        }
    
    def to_simple_dict(self) -> Dict[str, Any]:
        """Simplified state dictionary (for API responses)"""
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "status": self.status.value,
            "entities_count": self.entities_count,
            "profiles_count": self.profiles_count,
            "entity_types": self.entity_types,
            "config_generated": self.config_generated,
            "error": self.error,
        }


class SimulationManager:
    """
    Simulation Manager

    Core features:
    1. Read entities from graph and filter
    2. Generate Wonderwall Agent Profiles
    3. Use LLM to intelligently generate simulation configuration parameters
    4. Prepare all files needed by preset scripts
    """

    # Simulation data storage directory
    SIMULATION_DATA_DIR = os.path.join(
        os.path.dirname(__file__), 
        '../../uploads/simulations'
    )
    
    def __init__(self):
        # Ensure directory exists
        os.makedirs(self.SIMULATION_DATA_DIR, exist_ok=True)

        # In-memory simulation state cache
        self._simulations: Dict[str, SimulationState] = {}
    
    def _get_simulation_dir(self, simulation_id: str) -> str:
        """Get simulation data directory"""
        validate_simulation_id(simulation_id)
        sim_dir = os.path.join(self.SIMULATION_DATA_DIR, simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        return sim_dir
    
    def _save_simulation_state(self, state: SimulationState):
        """Save simulation state to file"""
        sim_dir = self._get_simulation_dir(state.simulation_id)
        state_file = os.path.join(sim_dir, "state.json")
        
        state.updated_at = datetime.now().isoformat()
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        
        self._simulations[state.simulation_id] = state
    
    def _load_simulation_state(self, simulation_id: str) -> Optional[SimulationState]:
        """Load simulation state from file"""
        if simulation_id in self._simulations:
            return self._simulations[simulation_id]
        
        sim_dir = self._get_simulation_dir(simulation_id)
        state_file = os.path.join(sim_dir, "state.json")
        
        if not os.path.exists(state_file):
            return None
        
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        state = SimulationState(
            simulation_id=simulation_id,
            project_id=data.get("project_id", ""),
            graph_id=data.get("graph_id", ""),
            enable_twitter=data.get("enable_twitter", True),
            enable_reddit=data.get("enable_reddit", True),
            enable_polymarket=data.get("enable_polymarket", False),
            polymarket_market_count=int(data.get("polymarket_market_count", 1) or 1),
            status=SimulationStatus(data.get("status", "created")),
            entities_count=data.get("entities_count", 0),
            profiles_count=data.get("profiles_count", 0),
            entity_types=data.get("entity_types", []),
            config_generated=data.get("config_generated", False),
            config_reasoning=data.get("config_reasoning", ""),
            current_round=data.get("current_round", 0),
            twitter_status=data.get("twitter_status", "not_started"),
            reddit_status=data.get("reddit_status", "not_started"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            error=data.get("error"),
            parent_simulation_id=data.get("parent_simulation_id"),
            config_diff=data.get("config_diff"),
            is_public=data.get("is_public", False),
        )
        
        self._simulations[simulation_id] = state
        return state
    
    def create_simulation(
        self,
        project_id: str,
        graph_id: str,
        enable_twitter: bool = True,
        enable_reddit: bool = True,
        enable_polymarket: bool = False,
        polymarket_market_count: int = 1,
    ) -> SimulationState:
        """
        Create a new simulation

        Args:
            project_id: Project ID
            graph_id: Graph ID
            enable_twitter: Whether to enable Twitter simulation
            enable_reddit: Whether to enable Reddit simulation
            enable_polymarket: Whether to enable Polymarket simulation

        Returns:
            SimulationState
        """
        import uuid
        simulation_id = f"sim_{uuid.uuid4().hex[:12]}"
        
        state = SimulationState(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            enable_twitter=enable_twitter,
            enable_reddit=enable_reddit,
            enable_polymarket=enable_polymarket,
            polymarket_market_count=max(1, min(5, int(polymarket_market_count or 1))),
            status=SimulationStatus.CREATED,
        )
        
        self._save_simulation_state(state)
        logger.info(f"Created simulation: {simulation_id}, project={project_id}, graph={graph_id}")
        
        return state
    
    def prepare_simulation(
        self,
        simulation_id: str,
        simulation_requirement: str,
        document_text: str,
        defined_entity_types: Optional[List[str]] = None,
        use_llm_for_profiles: bool = True,
        progress_callback: Optional[callable] = None,
        parallel_profile_count: int = 3,
        storage: 'GraphStorage' = None,
    ) -> SimulationState:
        """
        Prepare simulation environment (fully automated)

        Steps:
        1. Read and filter entities from graph
        2. Generate Wonderwall Agent Profile for each entity (optional LLM enhancement, supports parallelism)
        3. Use LLM to intelligently generate simulation config parameters (time, activity, posting frequency, etc.)
        4. Save config files and Profile files
        5. Copy preset scripts to simulation directory

        Args:
            simulation_id: Simulation ID
            simulation_requirement: Simulation requirement description (for LLM config generation)
            document_text: Original document content (for LLM background understanding)
            defined_entity_types: Predefined entity types (optional)
            use_llm_for_profiles: Whether to use LLM to generate detailed personas
            progress_callback: Progress callback function (stage, progress, message)
            parallel_profile_count: Number of personas to generate in parallel, default 3

        Returns:
            SimulationState
        """
        state = self._load_simulation_state(simulation_id)
        if not state:
            raise ValueError(f"Simulation does not exist: {simulation_id}")

        try:
            state.status = SimulationStatus.PREPARING
            self._save_simulation_state(state)

            # Pin simulation_id for the whole prep pipeline so every
            # downstream LLM call lands under the same Langfuse session.
            TraceContext.set(simulation_id=simulation_id)

            sim_dir = self._get_simulation_dir(simulation_id)

            # ========== Phase 1: Read and filter entities ==========
            if progress_callback:
                progress_callback("reading", 0, "Connecting to graph...")

            if not storage:
                raise ValueError("storage (GraphStorage) is required for prepare_simulation")
            reader = EntityReader(storage)

            if progress_callback:
                progress_callback("reading", 30, "Reading node data...")
            
            filtered = reader.filter_defined_entities(
                graph_id=state.graph_id,
                defined_entity_types=defined_entity_types,
                enrich_with_edges=True
            )
            
            state.entities_count = filtered.filtered_count
            state.entity_types = list(filtered.entity_types)
            
            if progress_callback:
                progress_callback(
                    "reading", 100,
                    f"Done, {filtered.filtered_count} entities in total",
                    current=filtered.filtered_count,
                    total=filtered.filtered_count
                )

            if filtered.filtered_count == 0:
                state.status = SimulationStatus.FAILED
                state.error = "No matching entities found, please check if the graph is built correctly"
                self._save_simulation_state(state)
                return state
            
            # ========== Phase 2: Generate Agent Profiles ==========
            total_entities = len(filtered.entities)

            if progress_callback:
                progress_callback(
                    "generating_profiles", 0,
                    "Starting generation...",
                    current=0,
                    total=total_entities
                )

            TraceContext.set(sim_phase="setup", prompt_type="persona_generation")

            # Pass graph_id to enable graph retrieval for richer context
            generator = WonderwallProfileGenerator(
                storage=storage,
                graph_id=state.graph_id,
                simulation_requirement=simulation_requirement,
            )
            
            def profile_progress(current, total, msg):
                if progress_callback:
                    progress_callback(
                        "generating_profiles", 
                        int(current / total * 100), 
                        msg,
                        current=current,
                        total=total,
                        item_name=msg
                    )
            
            # Set real-time save file path (prefer Reddit JSON format)
            realtime_output_path = None
            realtime_platform = "reddit"
            if state.enable_reddit:
                realtime_output_path = os.path.join(sim_dir, "reddit_profiles.json")
                realtime_platform = "reddit"
            elif state.enable_twitter:
                realtime_output_path = os.path.join(sim_dir, "twitter_profiles.csv")
                realtime_platform = "twitter"
            
            profiles = generator.generate_profiles_from_entities(
                entities=filtered.entities,
                use_llm=use_llm_for_profiles,
                progress_callback=profile_progress,
                graph_id=state.graph_id,  # Pass graph_id for graph retrieval
                parallel_count=parallel_profile_count,  # Parallel generation count
                realtime_output_path=realtime_output_path,  # Real-time save path
                output_platform=realtime_platform  # Output format
            )
            
            state.profiles_count = len(profiles)
            
            # Save Profile files (note: Twitter uses CSV format, Reddit uses JSON format)
            # Reddit profiles were already saved in real-time during generation; save again here to ensure completeness
            if progress_callback:
                progress_callback(
                    "generating_profiles", 95,
                    "Saving Profile files...",
                    current=total_entities,
                    total=total_entities
                )
            
            if state.enable_reddit:
                generator.save_profiles(
                    profiles=profiles,
                    file_path=os.path.join(sim_dir, "reddit_profiles.json"),
                    platform="reddit"
                )
            
            if state.enable_twitter:
                # Twitter uses CSV format! This is an Wonderwall requirement
                generator.save_profiles(
                    profiles=profiles,
                    file_path=os.path.join(sim_dir, "twitter_profiles.csv"),
                    platform="twitter"
                )

            if state.enable_polymarket:
                generator.save_profiles(
                    profiles=profiles,
                    file_path=os.path.join(sim_dir, "polymarket_profiles.json"),
                    platform="polymarket"
                )
            
            if progress_callback:
                progress_callback(
                    "generating_profiles", 100,
                    f"Done, {len(profiles)} Profiles in total",
                    current=len(profiles),
                    total=len(profiles)
                )

            # ========== Phase 3: LLM-powered simulation config generation ==========
            if progress_callback:
                progress_callback(
                    "generating_config", 0,
                    "Analyzing simulation requirements...",
                    current=0,
                    total=3
                )
            
            TraceContext.set(sim_phase="setup", prompt_type="sim_config")

            config_generator = SimulationConfigGenerator()

            if progress_callback:
                progress_callback(
                    "generating_config", 30,
                    "Calling LLM to generate config...",
                    current=1,
                    total=3
                )
            
            sim_params = config_generator.generate_config(
                simulation_id=simulation_id,
                project_id=state.project_id,
                graph_id=state.graph_id,
                simulation_requirement=simulation_requirement,
                document_text=document_text,
                entities=filtered.entities,
                enable_twitter=state.enable_twitter,
                enable_reddit=state.enable_reddit,
                polymarket_market_count=state.polymarket_market_count,
            )
            
            if progress_callback:
                progress_callback(
                    "generating_config", 70,
                    "Saving config files...",
                    current=2,
                    total=3
                )

            # Save config file
            config_path = os.path.join(sim_dir, "simulation_config.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(sim_params.to_json())
            
            state.config_generated = True
            state.config_reasoning = sim_params.generation_reasoning
            
            if progress_callback:
                progress_callback(
                    "generating_config", 100,
                    "Config generation complete",
                    current=3,
                    total=3
                )

            # Note: run scripts remain in backend/scripts/ directory, no longer copied to simulation directory
            # When starting simulation, simulation_runner will run scripts from the scripts/ directory

            # Clear per-phase tags so a follow-up call (e.g., re-prepare,
            # report generation) doesn't inherit "setup" context.
            TraceContext.set(sim_phase="", prompt_type="")

            # Update status
            state.status = SimulationStatus.READY
            self._save_simulation_state(state)
            
            logger.info(f"Simulation preparation complete: {simulation_id}, "
                       f"entities={state.entities_count}, profiles={state.profiles_count}")
            
            return state
            
        except Exception as e:
            logger.error(f"Simulation preparation failed: {simulation_id}, error={str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            state.status = SimulationStatus.FAILED
            state.error = str(e)
            self._save_simulation_state(state)
            raise
    
    def get_simulation(self, simulation_id: str) -> Optional[SimulationState]:
        """Get simulation state"""
        return self._load_simulation_state(simulation_id)
    
    def list_simulations(self, project_id: Optional[str] = None) -> List[SimulationState]:
        """List all simulations"""
        simulations = []

        if os.path.exists(self.SIMULATION_DATA_DIR):
            for sim_id in os.listdir(self.SIMULATION_DATA_DIR):
                # Skip hidden files (e.g. .DS_Store) and non-directory files
                sim_path = os.path.join(self.SIMULATION_DATA_DIR, sim_id)
                if sim_id.startswith('.') or not os.path.isdir(sim_path):
                    continue
                
                state = self._load_simulation_state(sim_id)
                if state:
                    if project_id is None or state.project_id == project_id:
                        simulations.append(state)
        
        return simulations
    
    def get_profiles(self, simulation_id: str, platform: str = "reddit") -> List[Dict[str, Any]]:
        """Get simulation Agent Profiles"""
        state = self._load_simulation_state(simulation_id)
        if not state:
            raise ValueError(f"Simulation does not exist: {simulation_id}")
        
        sim_dir = self._get_simulation_dir(simulation_id)
        profile_path = os.path.join(sim_dir, f"{platform}_profiles.json")
        
        if not os.path.exists(profile_path):
            return []
        
        with open(profile_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_simulation_config(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """Get simulation config"""
        sim_dir = self._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            return None
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def branch_counterfactual(
        self,
        parent_simulation_id: str,
        injection_text: str,
        trigger_round: int,
        label: Optional[str] = None,
        branch_id: Optional[str] = None,
    ) -> SimulationState:
        """Fork a simulation and schedule a counterfactual injection at trigger_round.

        Semantics (runner-contract):
            1. Forks the parent → new sim, READY to run (reuses profiles).
            2. Writes ``counterfactual_injection.json`` into the new sim's
               directory so ``run_parallel_simulation.py`` (or any future
               runner) can read it at round-start and inject ``injection_text``
               into every agent's observation prompt for rounds
               ``>= trigger_round``.
            3. Marks the new simulation's ``config_diff`` with the counterfactual
               metadata so the UI can highlight the branch lineage.

        The runner is expected to read the injection file; if it doesn't
        (older runner versions), the branch still runs — it just behaves
        identically to a plain fork. Graceful degradation.
        """
        import uuid

        if trigger_round < 0:
            raise ValueError("trigger_round must be >= 0")
        if not injection_text or not injection_text.strip():
            raise ValueError("injection_text is required")

        parent = self._load_simulation_state(parent_simulation_id)
        if not parent:
            raise ValueError(f"Parent simulation not found: {parent_simulation_id}")

        # Delegate the copy/profile machinery to the existing fork path so we
        # stay DRY.
        child = self.fork_simulation(parent_simulation_id=parent_simulation_id)

        injection_payload = {
            "parent_simulation_id": parent_simulation_id,
            "trigger_round": int(trigger_round),
            "injection_text": injection_text.strip(),
            "label": (label or f"counterfactual_{uuid.uuid4().hex[:6]}").strip(),
            "branch_id": branch_id,
            "created_at": datetime.now().isoformat(),
        }

        sim_dir = self._get_simulation_dir(child.simulation_id)
        injection_path = os.path.join(sim_dir, "counterfactual_injection.json")
        with open(injection_path, "w", encoding="utf-8") as fh:
            json.dump(injection_payload, fh, ensure_ascii=False, indent=2)

        diff = dict(child.config_diff or {})
        diff["counterfactual"] = {
            "trigger_round": injection_payload["trigger_round"],
            "label": injection_payload["label"],
            "preview": injection_payload["injection_text"][:140],
        }
        child.config_diff = diff
        child.config_reasoning = (
            f"Branched from {parent_simulation_id} with counterfactual "
            f"'{injection_payload['label']}' at round {trigger_round}"
        )
        self._save_simulation_state(child)

        logger.info(
            f"Counterfactual branch: {child.simulation_id} "
            f"<- {parent_simulation_id} @ r{trigger_round} ({injection_payload['label']})"
        )
        return child

    def fork_simulation(
        self,
        parent_simulation_id: str,
        simulation_requirement: Optional[str] = None,
    ) -> SimulationState:
        """
        Fork an existing simulation into a new child simulation.

        Copies all prepared files (profiles, config) from the parent so the
        child is immediately READY to run without going through the full
        prepare pipeline again.  The caller may override simulation_requirement
        to explore a different scenario with the same agent population.

        Args:
            parent_simulation_id: ID of the simulation to fork from
            simulation_requirement: Optional new scenario description.
                                    Defaults to the parent's requirement.

        Returns:
            New SimulationState with status=READY and parent_simulation_id set
        """
        import uuid

        parent = self._load_simulation_state(parent_simulation_id)
        if not parent:
            raise ValueError(f"Parent simulation not found: {parent_simulation_id}")

        parent_dir = self._get_simulation_dir(parent_simulation_id)

        # Create new simulation ID and directory
        new_id = f"sim_{uuid.uuid4().hex[:12]}"
        new_dir = self._get_simulation_dir(new_id)
        os.makedirs(new_dir, exist_ok=True)

        # Copy preparation files
        files_to_copy = [
            "reddit_profiles.json",
            "twitter_profiles.csv",
            "polymarket_profiles.json",
        ]
        for fname in files_to_copy:
            src = os.path.join(parent_dir, fname)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(new_dir, fname))

        # Copy and optionally patch the simulation config
        config_diff: Dict[str, Any] = {}
        parent_config_path = os.path.join(parent_dir, "simulation_config.json")
        if os.path.exists(parent_config_path):
            with open(parent_config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            original_requirement = config_data.get("simulation_requirement", "")

            if simulation_requirement and simulation_requirement != original_requirement:
                config_diff["simulation_requirement"] = {
                    "from": original_requirement,
                    "to": simulation_requirement,
                }
                config_data["simulation_requirement"] = simulation_requirement

            # Update IDs to point to the new simulation
            config_data["simulation_id"] = new_id

            new_config_path = os.path.join(new_dir, "simulation_config.json")
            with open(new_config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        else:
            if simulation_requirement:
                config_diff["simulation_requirement"] = {
                    "from": "",
                    "to": simulation_requirement,
                }

        state = SimulationState(
            simulation_id=new_id,
            project_id=parent.project_id,
            graph_id=parent.graph_id,
            enable_twitter=parent.enable_twitter,
            enable_reddit=parent.enable_reddit,
            enable_polymarket=parent.enable_polymarket,
            polymarket_market_count=parent.polymarket_market_count,
            status=SimulationStatus.READY,
            entities_count=parent.entities_count,
            profiles_count=parent.profiles_count,
            entity_types=list(parent.entity_types),
            config_generated=True,
            config_reasoning=f"Forked from {parent_simulation_id}",
            parent_simulation_id=parent_simulation_id,
            config_diff=config_diff if config_diff else None,
        )

        self._save_simulation_state(state)
        logger.info(
            f"Forked simulation: {new_id} from parent={parent_simulation_id}, "
            f"diff={config_diff}"
        )
        return state

    def get_run_instructions(self, simulation_id: str) -> Dict[str, str]:
        """Get run instructions"""
        sim_dir = self._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts'))
        
        return {
            "simulation_dir": sim_dir,
            "scripts_dir": scripts_dir,
            "config_file": config_path,
            "commands": {
                "twitter": f"python {scripts_dir}/run_twitter_simulation.py --config {config_path}",
                "reddit": f"python {scripts_dir}/run_reddit_simulation.py --config {config_path}",
                "parallel": f"python {scripts_dir}/run_parallel_simulation.py --config {config_path}",
            },
            "instructions": (
                f"1. Activate conda environment: conda activate MiroShark\n"
                f"2. Run simulation (scripts located at {scripts_dir}):\n"
                f"   - Run Twitter only: python {scripts_dir}/run_twitter_simulation.py --config {config_path}\n"
                f"   - Run Reddit only: python {scripts_dir}/run_reddit_simulation.py --config {config_path}\n"
                f"   - Run both platforms in parallel: python {scripts_dir}/run_parallel_simulation.py --config {config_path}"
            )
        }
