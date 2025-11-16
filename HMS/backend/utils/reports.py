import os
from datetime import date

from jinja2 import Template

REPORTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'reports')
if not os.path.exists(REPORTS_DIR):
    os.makedirs(REPORTS_DIR, exist_ok=True)


def generate_doctor_monthly_html(doctor, year, month, summary, appointments):
    """Create a simple HTML report for a doctor for given month.

    `summary` is a dict with totals. `appointments` is a list of serialized rows.
    Returns path to saved HTML file.
    """
    tpl = Template(
        """
    <html>
    <head><title>Monthly Report - {{ doctor.name }} - {{ year }}-{{ month }}</title></head>
    <body>
      <h1>Monthly Activity Report</h1>
      <h2>Doctor: {{ doctor.name }}</h2>
      <p>Month: {{ year }}-{{ month }}</p>
      <h3>Summary</h3>
      <ul>
        <li>Total appointments: {{ summary.total }}</li>
        <li>Completed: {{ summary.completed }}</li>
        <li>Cancelled: {{ summary.cancelled }}</li>
      </ul>

      <h3>Appointments</h3>
      <table border="1" cellpadding="4" cellspacing="0">
        <thead><tr><th>Date</th><th>Patient</th><th>Status</th><th>Diagnosis</th></tr></thead>
        <tbody>
        {% for a in appointments %}
          <tr>
            <td>{{ a.date }}</td>
            <td>{{ a.patient.name }}</td>
            <td>{{ a.status }}</td>
            <td>{{ a.treatment.diagnosis if a.treatment else '' }}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </body>
    </html>
    """
    )

    html = tpl.render(doctor=doctor, year=year, month=month, summary=summary, appointments=appointments)
    filename = f"doctor_{doctor.id}_{year}_{month}.html"
    path = os.path.join(REPORTS_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    return path
