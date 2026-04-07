/**
 * PDF export helpers using jsPDF + autoTable.
 */
import jsPDF from 'jspdf'
import autoTable from 'jspdf-autotable'

const BRAND_COLOR: [number, number, number] = [37, 99, 235] // blue-600

function addHeader(doc: jsPDF, title: string) {
  doc.setFillColor(...BRAND_COLOR)
  doc.rect(0, 0, doc.internal.pageSize.getWidth(), 38, 'F')
  doc.setTextColor(255, 255, 255)
  doc.setFontSize(18)
  doc.setFont('helvetica', 'bold')
  doc.text('Energy Saver AI', 14, 16)
  doc.setFontSize(11)
  doc.setFont('helvetica', 'normal')
  doc.text(title, 14, 28)
  // date on right
  const now = new Date().toLocaleString()
  doc.setFontSize(9)
  doc.text(now, doc.internal.pageSize.getWidth() - 14, 28, { align: 'right' })
  doc.setTextColor(0, 0, 0)
}

function addFooter(doc: jsPDF) {
  const pageCount = doc.getNumberOfPages()
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i)
    doc.setFontSize(8)
    doc.setTextColor(150)
    doc.text(
      `Page ${i} of ${pageCount}  |  Energy Saver AI © ${new Date().getFullYear()}`,
      doc.internal.pageSize.getWidth() / 2,
      doc.internal.pageSize.getHeight() - 8,
      { align: 'center' },
    )
  }
}

/** KPI cards → PDF table */
export function exportDashboardPDF(kpis: {
  total_consumption_kwh: number
  anomalies_detected: number
  occupancy_rate: number
  solar_generation_kwh: number
  current_tariff: number
  estimated_savings_today: number
  peak_demand_kw: number
}) {
  const doc = new jsPDF()
  addHeader(doc, 'Dashboard Report')

  autoTable(doc, {
    startY: 46,
    head: [['Metric', 'Value']],
    body: [
      ['Total Consumption', `${kpis.total_consumption_kwh.toFixed(2)} kWh`],
      ['Solar Generation', `${kpis.solar_generation_kwh.toFixed(2)} kWh`],
      ['Anomalies Detected', String(kpis.anomalies_detected)],
      ['Occupancy Rate', `${(kpis.occupancy_rate * 100).toFixed(0)}%`],
      ['Current Tariff', `Rs.${kpis.current_tariff.toFixed(2)}/kWh`],
      ['Estimated Savings', `Rs.${kpis.estimated_savings_today.toFixed(2)}`],
      ['Peak Demand', `${kpis.peak_demand_kw.toFixed(2)} kW`],
    ],
    theme: 'striped',
    headStyles: { fillColor: BRAND_COLOR },
  })

  addFooter(doc)
  doc.save('dashboard-report.pdf')
}

/** Bill prediction → PDF */
export function exportBillPDF(bill: {
  predicted_bill: number
  lower_bound: number
  upper_bound: number
  confidence_pct: number
  daily_budget: number
  remaining_budget: number
  days_elapsed: number
  kwh_so_far: number
  projected_kwh: number
}) {
  const doc = new jsPDF()
  addHeader(doc, 'Bill Prediction Report')

  autoTable(doc, {
    startY: 46,
    head: [['Metric', 'Value']],
    body: [
      ['Predicted Bill', `Rs.${bill.predicted_bill.toFixed(2)}`],
      ['Lower Bound', `Rs.${bill.lower_bound.toFixed(2)}`],
      ['Upper Bound', `Rs.${bill.upper_bound.toFixed(2)}`],
      ['Confidence', `${bill.confidence_pct.toFixed(0)}%`],
      ['Daily Budget', `Rs.${bill.daily_budget.toFixed(2)}`],
      ['Remaining Budget', `Rs.${bill.remaining_budget.toFixed(2)}`],
      ['Days Elapsed', String(bill.days_elapsed)],
      ['kWh So Far', `${bill.kwh_so_far.toFixed(2)} kWh`],
      ['Projected kWh', `${bill.projected_kwh.toFixed(2)} kWh`],
    ],
    theme: 'striped',
    headStyles: { fillColor: BRAND_COLOR },
  })

  addFooter(doc)
  doc.save('bill-prediction-report.pdf')
}

/** Anomaly table → PDF */
export function exportAnomaliesPDF(anomalies: {
  device_id: string
  timestamp: string
  anomaly_score: number
  is_anomaly: boolean
  consumption_kwh: number
}[]) {
  const doc = new jsPDF('landscape')
  addHeader(doc, 'Anomaly Detection Report')

  autoTable(doc, {
    startY: 46,
    head: [['Device', 'Timestamp', 'Score', 'Flagged', 'Consumption (kWh)']],
    body: anomalies.map((a) => [
      a.device_id,
      new Date(a.timestamp).toLocaleString(),
      a.anomaly_score.toFixed(4),
      a.is_anomaly ? 'YES' : 'No',
      a.consumption_kwh.toFixed(2),
    ]),
    theme: 'striped',
    headStyles: { fillColor: BRAND_COLOR },
    styles: { fontSize: 9 },
  })

  addFooter(doc)
  doc.save('anomalies-report.pdf')
}
