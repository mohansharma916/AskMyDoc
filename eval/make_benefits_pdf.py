"""Generate eval/corpus/benefits_guide.pdf, a multi-page PDF with a running
header and page numbers, so PDF parsing is covered by the fixed corpus.

    python eval/make_benefits_pdf.py
"""

from pathlib import Path

import pymupdf

OUT = Path(__file__).parent / "corpus" / "benefits_guide.pdf"
HEADER = "Northwind Robotics - Benefits Guide 2026"

PAGES = [
    [
        ("Northwind Benefits Guide", 22),
        ("This guide summarises employee benefits at Northwind Robotics, a fictional company", 11),
        ("used as a test corpus.", 11),
        ("Health Insurance", 16),
        ("Northwind pays 100% of the health insurance premium for employees and 75% for", 11),
        ("dependants. Coverage starts on the first day of employment. Employees choose", 11),
        ("between the Standard plan and the Plus plan during onboarding and during the", 11),
        ("open enrolment window every November.", 11),
        ("Dental and Vision", 16),
        ("Dental cover includes two check-ups per year. Vision cover reimburses up to 300 USD", 11),
        ("for glasses or contact lenses every two years.", 11),
    ],
    [
        ("Retirement", 16),
        ("Northwind matches retirement contributions up to 5% of base salary. The match vests", 11),
        ("immediately. Employees can change their contribution rate once per month.", 11),
        ("Learning and Development", 16),
        ("Each employee has an annual learning budget of 1,500 USD for courses, conferences,", 11),
        ("books and certifications. Unused learning budget does not roll over to the next", 11),
        ("year. Employees may also take up to 3 paid learning days per year to attend training.", 11),
        ("Wellbeing", 16),
        ("A monthly wellness stipend of 60 USD can be spent on gym memberships, fitness", 11),
        ("classes or therapy apps. Employees and their families can use the confidential", 11),
        ("Employee Assistance Programme for free counselling sessions.", 11),
    ],
    [
        ("Home Office and Commuting", 16),
        ("New employees receive a one-time home-office stipend of 750 USD for a desk, chair", 11),
        ("or monitor. Office-based employees receive a commuter allowance of 100 USD per", 11),
        ("month for public transport.", 11),
        ("Life and Disability Insurance", 16),
        ("Life insurance pays three times annual base salary. Long-term disability insurance", 11),
        ("covers 60% of base salary after 90 days of disability.", 11),
        ("Questions", 16),
        ("Questions about benefits go to the People Operations team through the #ask-people", 11),
        ("channel.", 11),
    ],
]


def build(path: Path = OUT) -> Path:
    doc = pymupdf.open()
    for n, lines in enumerate(PAGES, start=1):
        page = doc.new_page()
        page.insert_text((72, 40), HEADER, fontsize=8)
        y = 90
        for text, size in lines:
            if size > 11:
                y += 8
            page.insert_text((72, y), text, fontsize=size)
            y += size * 1.9
        page.insert_text((72, 810), f"Page {n} of {len(PAGES)}", fontsize=8)
    doc.set_metadata({"title": "Northwind Benefits Guide"})
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path, garbage=4, deflate=True, no_new_id=True)
    doc.close()
    return path


if __name__ == "__main__":
    print(build())
