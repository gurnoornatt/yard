"""Generate the three demo broker OM PDFs for the Sentinel hackathon demo."""

from fpdf import FPDF
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "demo_oms"
OUT.mkdir(exist_ok=True)

PROPERTIES = [
    {
        "filename": "mccullough_om.pdf",
        "title": "OFFERING MEMORANDUM",
        "subtitle": "4123 McCullough Ave - 32-Unit Multifamily",
        "location": "San Antonio, Texas 78212",
        "lines": [
            "EXCLUSIVELY OFFERED BY: Marcus & Millichap",
            "",
            "PROPERTY OVERVIEW",
            "Address:        4123 McCullough Ave, San Antonio, TX 78212",
            "Total Units:    32",
            "Year Built:     1972",
            "Asset Class:    Class C",
            "Asking Price:   $4,800,000  ($150,000/unit)",
            "",
            "EXECUTIVE SUMMARY",
            "Rare value-add opportunity in the Heart of San Antonio.",
            "Well-maintained 32-unit garden-style community with strong",
            "occupancy and below-market rents offering immediate upside",
            "through light renovation and rent optimization.",
            "",
            "UNIT MIX",
            "16 x 1BR/1BA  ~650 SF  Current Rent: $875/mo",
            "12 x 2BR/1BA  ~850 SF  Current Rent: $1,050/mo",
            " 4 x 2BR/2BA  ~950 SF  Current Rent: $1,150/mo",
            "",
            "FINANCIAL HIGHLIGHTS",
            "Gross Potential Rent:  $422,400/yr",
            "Occupancy (trailing):  94%",
            "NOI (trailing 12mo):   $224,000",
            "Cap Rate (asking):     4.67%",
            "",
            "LOCATION",
            "Located 1.2 miles from Pearl District. Strong walkability.",
            "Proximity to UTSA downtown campus drives renter demand.",
            "",
            "CONTACT",
            "Marcus & Millichap - San Antonio Office",
            "Broker: J. Rivera   DRE# TX-012345",
        ],
    },
    {
        "filename": "blanco_om.pdf",
        "title": "OFFERING MEMORANDUM",
        "subtitle": "7821 Blanco Rd - 48-Unit Multifamily",
        "location": "San Antonio, Texas 78216",
        "lines": [
            "EXCLUSIVELY OFFERED BY: CBRE",
            "",
            "PROPERTY OVERVIEW",
            "Address:        7821 Blanco Rd, San Antonio, TX 78216",
            "Total Units:    48",
            "Year Built:     2005",
            "Asset Class:    Class B",
            "Asking Price:   $9,200,000  ($191,667/unit)",
            "",
            "EXECUTIVE SUMMARY",
            "Trophy Class B asset in the rapidly appreciating NW San Antonio",
            "corridor. Recent elevator modernization and institutional-quality",
            "management in place. Priced to reflect the premier location and",
            "recent capital investment.",
            "",
            "UNIT MIX",
            "24 x 1BR/1BA  ~750 SF  Current Rent: $1,150/mo",
            "20 x 2BR/2BA  ~1,050 SF  Current Rent: $1,425/mo",
            " 4 x 3BR/2BA  ~1,250 SF  Current Rent: $1,750/mo",
            "",
            "FINANCIAL HIGHLIGHTS",
            "Gross Potential Rent:  $804,000/yr",
            "Occupancy (trailing):  91%",
            "NOI (trailing 12mo):   $368,000",
            "Cap Rate (asking):     4.00%",
            "",
            "RECENT CAPITAL IMPROVEMENTS",
            "2024: Elevator modernization       $180,000",
            "2024: Electrical panel upgrades    $ 42,000",
            "Total recent capex:                $222,000",
            "",
            "CONTACT",
            "CBRE - San Antonio Multifamily",
            "Broker: A. Morales   DRE# TX-098765",
        ],
    },
    {
        "filename": "culebra_om.pdf",
        "title": "OFFERING MEMORANDUM",
        "subtitle": "2455 Culebra Rd - 24-Unit Multifamily",
        "location": "San Antonio, Texas 78228",
        "lines": [
            "EXCLUSIVELY OFFERED BY: Whitestone Real Estate",
            "",
            "PROPERTY OVERVIEW",
            "Address:        2455 Culebra Rd, San Antonio, TX 78228",
            "Total Units:    24",
            "Year Built:     1988",
            "Asset Class:    Class C",
            "Asking Price:   $3,100,000  ($129,167/unit)",
            "",
            "EXECUTIVE SUMMARY",
            "Solid West Side cash-flowing asset with stable tenancy and",
            "recent roof replacement. Owner retiring after 6 years of",
            "stewardship. Priced for a quick close.",
            "",
            "UNIT MIX",
            "12 x 1BR/1BA  ~620 SF  Current Rent: $825/mo",
            "10 x 2BR/1BA  ~820 SF  Current Rent: $975/mo",
            " 2 x 2BR/2BA  ~900 SF  Current Rent: $1,075/mo",
            "",
            "FINANCIAL HIGHLIGHTS",
            "Gross Potential Rent:  $263,400/yr",
            "Occupancy (trailing):  96%",
            "NOI (trailing 12mo):   $148,000",
            "Cap Rate (asking):     4.77%",
            "",
            "RECENT CAPITAL IMPROVEMENTS",
            "2024: Complete roof replacement    $38,000",
            "",
            "CONTACT",
            "Whitestone Real Estate - San Antonio",
            "Broker: T. Nguyen   DRE# TX-054321",
        ],
    },
]


def generate(prop: dict) -> None:
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 12, prop["title"], new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, prop["subtitle"], new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 7, prop["location"], new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(6)

    pdf.set_draw_color(180, 180, 180)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(6)

    pdf.set_font("Courier", "", 10)
    for line in prop["lines"]:
        if line == line.upper() and line.strip():
            pdf.set_font("Courier", "B", 10)
            pdf.cell(0, 6, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Courier", "", 10)
        else:
            pdf.cell(0, 6, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    out_path = OUT / prop["filename"]
    pdf.output(str(out_path))
    print(f"  created: {out_path}")


if __name__ == "__main__":
    print("Generating demo OM PDFs...")
    for prop in PROPERTIES:
        generate(prop)
    print("Done. Files are in demo_oms/")
