report = env.ref("sale.action_report_saleorder")
html = """
<html>
<head>
<meta charset="utf-8">
<style>
@font-face {
    font-family: "Phetsarath OT";
    src: url("/sale_quotation_ss_report/static/src/fonts/Phetsarath_OT.ttf");
}
body { font-family: "Phetsarath OT"; font-size: 24px; }
</style>
</head>
<body>
ພະນັກງານຂາຍ ລາຄາຕໍ່ຫົວໜ່ວຍ ຜູ້ອະນຸມັດຊື້
ລວມເງິນ ອາກອນມູນຄ່າເພີ່ມ ລວມທັງໝົດ
</body>
</html>
"""
pdf = report._run_wkhtmltopdf(
    [html],
    report_ref=report.report_name,
)
with open("/tmp/server_quote.pdf", "wb") as pdf_file:
    pdf_file.write(pdf)
print("PDF_RESULT", len(pdf), "pdf")
