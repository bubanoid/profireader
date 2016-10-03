from .blueprints_declaration import tutorial_bp
from flask import render_template
from .request_wrapers import ok, check_right
from ..models.rights import AllowAll


@tutorial_bp.route('/')
@check_right(AllowAll)
def index():
    return render_template('/tutorial.html')
