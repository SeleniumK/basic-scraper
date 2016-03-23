import requests
import io
import sys
from bs4 import BeautifulSoup
# import geocoder


INSPECTION_DOMAIN = "http://info.kingcounty.gov"
INSPECTION_PATH = "/health/ehs/foodsafety/inspections/Results.aspx"
INSPECTION_PARAMS = {
    "Output": "W",
    "Business_Name": "",
    "Business_Address": "",
    "Longitude": "",
    "Latitude": "",
    "City": "",
    "Zip_Code": "",
    "Inspection_Type": "All",
    "Inspection_Start": "",
    "Inspection_End": "",
    "Inspection_Closed_Business": "A",
    "Violation_Points": "",
    "Violation_Red_Points": "",
    "Violation_Descr": "",
    "Fuzzy_Search": "N",
    "Sort": "B",
}


def get_inspection_page(**kwargs):
    url = INSPECTION_DOMAIN + INSPECTION_PATH
    params = INSPECTION_PARAMS.copy()
    for key, value in kwargs.items():
        if key in params:
            params[key] = value
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.text, response.encoding


def write_to_file(text, filename):
    with open(filename, "w") as f:
        f.write(text)


def write_to_inspection_page(filename, **kwargs):
    text, encoding = get_inspection_page(**kwargs)
    write_to_file(text, filename)


def load_inspection_page(fh):
    file = io.open(fh, encoding='utf-8')
    file_text = file.read()
    file.close()
    return file_text


def beautify_html(html):
    return BeautifulSoup(html, "html5lib")


def extract_data_listings(html):
    return html.findAll('div', {"id": lambda x: x and x.startswith('PR') and x.endswith("~")})


def has_two_tds(element):
    is_tr = element.name == 'tr'
    tdchildren = element.findAll('td', recursive=False)
    two_children = len(tdchildren) == 2
    return is_tr and two_children


def clean_data(cell):
    text = cell.string
    try:
        return text.strip(' \n:-')
    except AttributeError:
        return u""


def extract_restaurant_metadata(element):
    metadata_rows = element.find('tbody').findAll(has_two_tds, recursive=False)
    data = {}
    current_label = ""
    for row in metadata_rows:
        key, value = row.findAll('td', recursive=False)
        new_lable = clean_data(key)
        current_label = new_lable if new_lable else current_label
        data.setdefault(current_label, []).append(clean_data(value))
    return data


def is_inspection_row(element):
    keyword = "inspection"
    is_tr = element.name == 'tr'
    if not is_tr:
        return False
    tdchildren = element.findAll('td', recursive=False)
    four_children = len(tdchildren) == 4
    text = clean_data(tdchildren[0]).lower()
    has_word = keyword in text
    does_not_start = not text.startswith(keyword)
    return is_tr and four_children and has_word and does_not_start


def extract_score_data(listing):
    inspection_rows = listing.find_all(is_inspection_row)
    samples = len(inspection_rows)
    total = high_score = average = 0
    for row in inspection_rows:
        str_val = clean_data(row.find_all('td')[2])
        int_val = int(str_val)
        total += int_val
        high_score = int_val if int_val > high_score else high_score
    if samples:
        average = total / float(samples)
    data = {
        "Total Inspections": samples,
        "Average": average,
        "High Score": high_score,
    }
    return data


def generate_results(real_call=False):
    args = {
        "Zip_Code": "98101",
        "Inspection_Start": "03/03/2014",
        "Inspection_End": "03/03/2016",
    }
    fh = "inspection_page.html"

    if real_call:
        write_to_inspection_page(fh, **args)

    text = load_inspection_page(fh)
    parsed = beautify_html(text)
    listings = extract_data_listings(parsed)
    for listing in listings:
        metadata = extract_restaurant_metadata(listing)
        inspection_row = listing.find_all(is_inspection_row)
        score_data = extract_score_data(listing)
        metadata.update(score_data)
        yield metadata


def get_geojson(results):
    address = " ".join(results.get("Address", []))
    if address is None:
        return None
    else:
        response = geocoder.google(address)
        return response.geojson


if __name__ == "__main__":
    real_call = len(sys.argv) > 1 and sys.argv[1] == 'real_call'
    for result in generate_results(real_call):
        print(result)
