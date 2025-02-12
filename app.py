from flask import Flask, Response
from apscheduler.schedulers.background import BackgroundScheduler
from scraper import update_opportunities, XML_FILE_PATH
import os

app = Flask(__name__)

def scheduled_update():
    print("Updating...")
    update_opportunities()
    print("Update is over.")

# Creates background task for executing update function with interval
if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
  sched = BackgroundScheduler()
  sched.add_job(scheduled_update, "interval", minutes=1)
  sched.start()

@app.route("/", methods=["GET"])
def serve_xml():
    """ Returns XML file """
    if os.path.exists(XML_FILE_PATH):
        with open(XML_FILE_PATH, "r", encoding="utf-8") as f:
            xml_data = f.read()
        return Response(xml_data, mimetype="application/xml")
    return "XML file not found!", 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
