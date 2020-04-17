
causes_of_death = {
    'Heart Disease': 647457,
    'Cancer': 599108,
    'Accidents': 169936,
    'CLRD': 160201,
    'Stroke': 146383,
    'Alzheimer': 121404,
    'Diabetes': 83564,
    'Flu&Pneumonia': 55672,
    'Kidney Disease': 50633,
    'Suicide': 47173,
    'All Other Causes': 731972,
}

def s(x):
    if x == 'All Other Causes':
        return 0
    else:
        return causes_of_death[x]

def get_causes():
    return [(x, causes_of_death[x]) for x in sorted(causes_of_death, key=s)[::-1]]
