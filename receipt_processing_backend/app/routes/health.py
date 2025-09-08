from flask_smorest import Blueprint
from flask.views import MethodView

blp = Blueprint("Health", "health", url_prefix="/", description="Health check route for uptime verification")


@blp.route("/")
class HealthCheck(MethodView):
    """Health check endpoint."""
    def get(self):
        """Return basic health status."""
        return {"message": "Healthy"}
