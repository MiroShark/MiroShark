"""
API Routes Module
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)
decision_lab_bp = Blueprint('decision_lab', __name__)
seed_chat_bp = Blueprint('seed_chat', __name__)

from . import graph  # noqa: E402, F401
from . import simulation  # noqa: E402, F401
from . import report  # noqa: E402, F401
from . import decision_lab  # noqa: E402, F401
from . import seed_chat  # noqa: E402, F401
from . import decision_tree_public  # noqa: E402, F401
from . import education  # noqa: E402, F401
from . import infographics  # noqa: E402, F401
from . import narration  # noqa: E402, F401

