"""
Report API routes
Provides simulation report generation, retrieval, and conversation endpoints
"""

import os
import traceback
import threading
from flask import request, jsonify, send_file, current_app

from . import report_bp
from ..services.report_agent import ReportAgent, ReportManager, ReportStatus
from ..services.graph_tools import GraphToolsService
from ..services.simulation_manager import SimulationManager
from ..models.project import ProjectManager
from ..models.task import TaskManager, TaskStatus
from ..utils.logger import get_logger
from ..utils.i18n import get_locale, t as _t
from ..utils.validation import validate_simulation_id

logger = get_logger('miroshark.api.report')


@report_bp.before_request
def _validate_url_simulation_id():
    """Reject requests whose URL-derived simulation_id could cause path traversal."""
    from flask import request as _req
    sim_id = _req.view_args.get('simulation_id') if _req.view_args else None
    if sim_id is not None:
        try:
            validate_simulation_id(sim_id)
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400


# ============== Report Generation Endpoints ==============

@report_bp.route('/generate', methods=['POST'])
def generate_report():
    """
    Generate simulation analysis report (async task)

    This is a time-consuming operation. The endpoint returns task_id immediately.
    Use GET /api/report/generate/status to query progress.

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",    // Required, simulation ID
            "force_regenerate": false        // Optional, force regeneration
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "task_id": "task_xxxx",
                "status": "generating",
                "message": "Report generation task started"
            }
        }
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": _t("Please provide simulation_id", "请提供 simulation_id", locale)
            }), 400
        try:
            validate_simulation_id(simulation_id)
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

        force_regenerate = data.get('force_regenerate', False)

        # Get simulation info
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)

        if not state:
            return jsonify({
                "success": False,
                "error": _t(f"Simulation not found: {simulation_id}", f"未找到模拟:{simulation_id}", locale)
            }), 404

        # Check if a report already exists
        if not force_regenerate:
            existing_report = ReportManager.get_report_by_simulation(simulation_id)
            if existing_report and existing_report.status == ReportStatus.COMPLETED:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "report_id": existing_report.report_id,
                        "status": "completed",
                        "message": "Report already exists",
                        "already_generated": True
                    }
                })

        # Get project info
        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": _t(f"Project not found: {state.project_id}", f"未找到项目:{state.project_id}", locale)
            }), 404

        graph_id = state.graph_id or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": _t(
                    "Missing graph ID, please ensure the graph has been built",
                    "缺少图谱 ID,请确认图谱已构建完成",
                    locale,
                )
            }), 400

        simulation_requirement = project.simulation_requirement
        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": _t("Missing simulation requirement description", "缺少模拟需求描述", locale)
            }), 400

        # Pre-generate report_id for immediate return to frontend
        import uuid
        report_id = f"report_{uuid.uuid4().hex[:12]}"

        # Create async task
        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="report_generate",
            metadata={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "report_id": report_id
            }
        )

        # Initialize graph_tools in Flask context BEFORE spawning thread
        # (current_app is not available inside background threads)
        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            return jsonify({
                "success": False,
                "error": _t("Neo4j storage not initialized", "Neo4j 存储尚未初始化", locale)
            }), 503
        graph_tools = GraphToolsService(storage=storage)

        # Define background task
        def run_generate():
            try:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=0,
                    message="Initializing Report Agent..."
                )

                # Create Report Agent
                agent = ReportAgent(
                    graph_id=graph_id,
                    simulation_id=simulation_id,
                    simulation_requirement=simulation_requirement,
                    graph_tools=graph_tools
                )

                # Progress callback
                def progress_callback(stage, progress, message):
                    task_manager.update_task(
                        task_id,
                        progress=progress,
                        message=f"[{stage}] {message}"
                    )

                # Generate report (pass pre-generated report_id)
                report = agent.generate_report(
                    progress_callback=progress_callback,
                    report_id=report_id
                )

                # Save report
                ReportManager.save_report(report)

                if report.status == ReportStatus.COMPLETED:
                    task_manager.complete_task(
                        task_id,
                        result={
                            "report_id": report.report_id,
                            "simulation_id": simulation_id,
                            "status": "completed"
                        }
                    )
                else:
                    task_manager.fail_task(task_id, report.error or "Report generation failed")

            except Exception as e:
                logger.error(f"Report generation failed: {str(e)}")
                task_manager.fail_task(task_id, str(e))

        # Start background thread
        thread = threading.Thread(target=run_generate, daemon=True)
        thread.start()

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "report_id": report_id,
                "task_id": task_id,
                "status": "generating",
                "message": "Report generation task started, query progress via /api/report/generate/status",
                "already_generated": False
            }
        })

    except Exception as e:
        logger.error(f"Failed to start report generation task: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/generate/status', methods=['POST'])
def get_generate_status():
    """
    Query report generation task progress

    Request (JSON):
        {
            "task_id": "task_xxxx",         // Optional, task_id returned by generate
            "simulation_id": "sim_xxxx"     // Optional, simulation ID
        }

    Returns:
        {
            "success": true,
            "data": {
                "task_id": "task_xxxx",
                "status": "processing|completed|failed",
                "progress": 45,
                "message": "..."
            }
        }
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        task_id = data.get('task_id')
        simulation_id = data.get('simulation_id')
        if simulation_id:
            try:
                validate_simulation_id(simulation_id)
            except ValueError as exc:
                return jsonify({"success": False, "error": str(exc)}), 400

        # If simulation_id is provided, first check if a completed report exists
        if simulation_id:
            existing_report = ReportManager.get_report_by_simulation(simulation_id)
            if existing_report and existing_report.status == ReportStatus.COMPLETED:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "report_id": existing_report.report_id,
                        "status": "completed",
                        "progress": 100,
                        "message": "Report has been generated",
                        "already_completed": True
                    }
                })

        if not task_id:
            return jsonify({
                "success": False,
                "error": _t(
                    "Please provide task_id or simulation_id",
                    "请提供 task_id 或 simulation_id",
                    locale,
                )
            }), 400

        task_manager = TaskManager()
        task = task_manager.get_task(task_id)

        if not task:
            return jsonify({
                "success": False,
                "error": _t(f"Task not found: {task_id}", f"未找到任务:{task_id}", locale)
            }), 404

        return jsonify({
            "success": True,
            "data": task.to_dict()
        })

    except Exception as e:
        logger.error(f"Failed to query task status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Report Retrieval Endpoints ==============

@report_bp.route('/<report_id>', methods=['GET'])
def get_report(report_id: str):
    """
    Get report details

    Returns:
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                "simulation_id": "sim_xxxx",
                "status": "completed",
                "outline": {...},
                "markdown_content": "...",
                "created_at": "...",
                "completed_at": "..."
            }
        }
    """
    locale = get_locale(request)
    try:
        report = ReportManager.get_report(report_id)

        if not report:
            return jsonify({
                "success": False,
                "error": _t(f"Report not found: {report_id}", f"未找到报告:{report_id}", locale)
            }), 404

        return jsonify({
            "success": True,
            "data": report.to_dict()
        })

    except Exception as e:
        logger.error(f"Failed to get report: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/by-simulation/<simulation_id>', methods=['GET'])
def get_report_by_simulation(simulation_id: str):
    """
    Get report by simulation ID

    Returns:
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                ...
            }
        }
    """
    locale = get_locale(request)
    try:
        report = ReportManager.get_report_by_simulation(simulation_id)

        if not report:
            return jsonify({
                "success": False,
                "error": _t(
                    f"No report available for this simulation: {simulation_id}",
                    f"该模拟尚无可用报告:{simulation_id}",
                    locale,
                ),
                "has_report": False
            }), 404

        return jsonify({
            "success": True,
            "data": report.to_dict(),
            "has_report": True
        })

    except Exception as e:
        logger.error(f"Failed to get report: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/download', methods=['GET'])
def download_report(report_id: str):
    """
    Download report (Markdown format)

    Returns a Markdown file
    """
    locale = get_locale(request)
    try:
        report = ReportManager.get_report(report_id)

        if not report:
            return jsonify({
                "success": False,
                "error": _t(f"Report not found: {report_id}", f"未找到报告:{report_id}", locale)
            }), 404

        md_path = ReportManager._get_report_markdown_path(report_id)

        if not os.path.exists(md_path):
            # If MD file does not exist, generate a temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write(report.markdown_content)
                temp_path = f.name

            return send_file(
                temp_path,
                as_attachment=True,
                download_name=f"{report_id}.md"
            )

        return send_file(
            md_path,
            as_attachment=True,
            download_name=f"{report_id}.md"
        )

    except Exception as e:
        logger.error(f"Failed to download report: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>', methods=['DELETE'])
def delete_report(report_id: str):
    """Delete report"""
    locale = get_locale(request)
    try:
        success = ReportManager.delete_report(report_id)

        if not success:
            return jsonify({
                "success": False,
                "error": _t(f"Report not found: {report_id}", f"未找到报告:{report_id}", locale)
            }), 404

        return jsonify({
            "success": True,
            "message": f"Report deleted: {report_id}"
        })

    except Exception as e:
        logger.error(f"Failed to delete report: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Report Agent Chat Endpoints ==============

@report_bp.route('/chat', methods=['POST'])
def chat_with_report_agent():
    """
    Chat with Report Agent

    Report Agent can autonomously call retrieval tools during conversation to answer questions

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",        // Required, simulation ID
            "message": "Please explain the trend",  // Required, user message
            "chat_history": [                   // Optional, conversation history
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]
        }

    Returns:
        {
            "success": true,
            "data": {
                "response": "Agent response...",
                "tool_calls": [list of tool calls],
                "sources": [information sources]
            }
        }
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        message = data.get('message')
        chat_history = data.get('chat_history', [])

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": _t("Please provide simulation_id", "请提供 simulation_id", locale)
            }), 400
        try:
            validate_simulation_id(simulation_id)
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

        if not message:
            return jsonify({
                "success": False,
                "error": _t("Please provide message", "请提供 message", locale)
            }), 400

        # Get simulation and project info
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)

        if not state:
            return jsonify({
                "success": False,
                "error": _t(f"Simulation not found: {simulation_id}", f"未找到模拟:{simulation_id}", locale)
            }), 404

        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": _t(f"Project not found: {state.project_id}", f"未找到项目:{state.project_id}", locale)
            }), 404

        graph_id = state.graph_id or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": _t("Missing graph ID", "缺少图谱 ID", locale)
            }), 400

        simulation_requirement = project.simulation_requirement or ""

        # Create Agent and start conversation
        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            return jsonify({
                "success": False,
                "error": _t("Neo4j storage not initialized", "Neo4j 存储尚未初始化", locale)
            }), 503
        graph_tools = GraphToolsService(storage=storage)

        agent = ReportAgent(
            graph_id=graph_id,
            simulation_id=simulation_id,
            simulation_requirement=simulation_requirement,
            graph_tools=graph_tools
        )

        result = agent.chat(message=message, chat_history=chat_history)

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        logger.error(f"Chat failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Report Progress and Section Endpoints ==============

# ============== Report Status Check Endpoints ==============

@report_bp.route('/check/<simulation_id>', methods=['GET'])
def check_report_status(simulation_id: str):
    """
    Check if a simulation has a report and its status

    Used by frontend to determine whether to unlock Interview feature

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "has_report": true,
                "report_status": "completed",
                "report_id": "report_xxxx",
                "interview_unlocked": true
            }
        }
    """
    try:
        report = ReportManager.get_report_by_simulation(simulation_id)

        has_report = report is not None
        report_status = report.status.value if report else None
        report_id = report.report_id if report else None

        # Only unlock interview after report is completed
        interview_unlocked = has_report and report.status == ReportStatus.COMPLETED

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "has_report": has_report,
                "report_status": report_status,
                "report_id": report_id,
                "interview_unlocked": interview_unlocked
            }
        })

    except Exception as e:
        logger.error(f"Failed to check report status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Agent Log Endpoints ==============

@report_bp.route('/<report_id>/agent-log', methods=['GET'])
def get_agent_log(report_id: str):
    """
    Get Report Agent's detailed execution log

    Retrieve each step of action during report generation in real-time, including:
    - Report start, planning start/complete
    - Each section's start, tool calls, LLM responses, completion
    - Report complete or failed

    Query parameters:
        from_line: Start reading from this line (optional, default 0, for incremental retrieval)

    Returns:
        {
            "success": true,
            "data": {
                "logs": [
                    {
                        "timestamp": "2025-12-13T...",
                        "elapsed_seconds": 12.5,
                        "report_id": "report_xxxx",
                        "action": "tool_call",
                        "stage": "generating",
                        "section_title": "Executive Summary",
                        "section_index": 1,
                        "details": {
                            "tool_name": "insight_forge",
                            "parameters": {...},
                            ...
                        }
                    },
                    ...
                ],
                "total_lines": 25,
                "from_line": 0,
                "has_more": false
            }
        }
    """
    try:
        from_line = request.args.get('from_line', 0, type=int)

        log_data = ReportManager.get_agent_log(report_id, from_line=from_line)

        return jsonify({
            "success": True,
            "data": log_data
        })

    except Exception as e:
        logger.error(f"Failed to get Agent log: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/agent-log/stream', methods=['GET'])
def stream_agent_log(report_id: str):
    """
    Get complete Agent log (fetch all at once)

    Returns:
        {
            "success": true,
            "data": {
                "logs": [...],
                "count": 25
            }
        }
    """
    try:
        logs = ReportManager.get_agent_log_stream(report_id)

        return jsonify({
            "success": True,
            "data": {
                "logs": logs,
                "count": len(logs)
            }
        })

    except Exception as e:
        logger.error(f"Failed to get Agent log: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Console Log Endpoints ==============

@report_bp.route('/<report_id>/console-log', methods=['GET'])
def get_console_log(report_id: str):
    """
    Get Report Agent's console output log

    Retrieve console output (INFO, WARNING, etc.) during report generation in real-time.
    This differs from the structured JSON log returned by the agent-log endpoint;
    it is plain text console-style log.

    Query parameters:
        from_line: Start reading from this line (optional, default 0, for incremental retrieval)

    Returns:
        {
            "success": true,
            "data": {
                "logs": [
                    "[19:46:14] INFO: Search complete: found 15 related facts",
                    "[19:46:14] INFO: Graph search: graph_id=xxx, query=...",
                    ...
                ],
                "total_lines": 100,
                "from_line": 0,
                "has_more": false
            }
        }
    """
    try:
        from_line = request.args.get('from_line', 0, type=int)

        log_data = ReportManager.get_console_log(report_id, from_line=from_line)

        return jsonify({
            "success": True,
            "data": log_data
        })

    except Exception as e:
        logger.error(f"Failed to get console log: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/console-log/stream', methods=['GET'])
def stream_console_log(report_id: str):
    """
    Get complete console log (fetch all at once)

    Returns:
        {
            "success": true,
            "data": {
                "logs": [...],
                "count": 100
            }
        }
    """
    try:
        logs = ReportManager.get_console_log_stream(report_id)

        return jsonify({
            "success": True,
            "data": {
                "logs": logs,
                "count": len(logs)
            }
        })

    except Exception as e:
        logger.error(f"Failed to get console log: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Tool Call Endpoints (for debugging) ==============

@report_bp.route('/tools/search', methods=['POST'])
def search_graph_tool():
    """
    Graph search tool endpoint (for debugging)

    Request (JSON):
        {
            "graph_id": "miroshark_xxxx",
            "query": "search query",
            "limit": 10
        }
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        graph_id = data.get('graph_id')
        query = data.get('query')
        limit = data.get('limit', 10)

        if not graph_id or not query:
            return jsonify({
                "success": False,
                "error": _t("Please provide graph_id and query", "请提供 graph_id 和 query", locale)
            }), 400

        from flask import current_app
        from ..services.graph_tools import GraphToolsService

        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            return jsonify({
                "success": False,
                "error": _t("Neo4j storage is not initialized", "Neo4j 存储尚未初始化", locale)
            }), 503

        tools = GraphToolsService(storage=storage)
        result = tools.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit
        )

        return jsonify({
            "success": True,
            "data": result.to_dict()
        })

    except Exception as e:
        logger.error(f"Graph search failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/tools/statistics', methods=['POST'])
def get_graph_statistics_tool():
    """
    Graph statistics tool endpoint (for debugging)

    Request (JSON):
        {
            "graph_id": "miroshark_xxxx"
        }
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        graph_id = data.get('graph_id')

        if not graph_id:
            return jsonify({
                "success": False,
                "error": _t("Please provide graph_id", "请提供 graph_id", locale)
            }), 400

        from flask import current_app
        from ..services.graph_tools import GraphToolsService

        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            return jsonify({
                "success": False,
                "error": _t("Neo4j storage is not initialized", "Neo4j 存储尚未初始化", locale)
            }), 503

        tools = GraphToolsService(storage=storage)
        result = tools.get_graph_statistics(graph_id)

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        logger.error(f"Failed to get graph statistics: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
