# agc-error
Compare error of multiple autogeocoded datasets with human geocoded dataset


compare.py takes country name as input (must match country folder name)

each country folder contains:

- "alt" directory: holds autogeocoded datasets
- "results" directory: used to store JSON output files from compare.py
- "shapefiles" directory: stores shapefiles for the ADM levels at which error is being calculated
- "actual.csv" file: human geocoded dataset
