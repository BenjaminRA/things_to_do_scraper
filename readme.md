# Cities database

All the data of the cities, states and countries of the world has been provided by the [🌍 Countries States Cities Database](https://github.com/dr5hn/countries-states-cities-database).

# Setting up from scratch

## Python

Download the installer from [https://www.python.org/downloads](https://www.python.org/downloads)

When you run the installer, you have to check the box labeled `Add Python X.XX to PATH`.

## Code

If you don't have git, you can download this code clicking on the green button at the top right corner labeled `Code`. Then click on `Download ZIP` and unzip the file.

## Python libraries

Open a terminal and navigate the folder where you unzipped the code.
Once you are in the folder, run the following command:

```
pip install -r requirements.txt
```

## Credentials

Create a `.env` file in the root folder of the project. Copy the following content:

```
MONGODB_HOST=XXXXXXXXXX
MONGODB_USER=XXXXXXXXXX
MONGODB_PASSWORD=XXXXXXXXXX
MONGODB_DBNAME=XXXXXXXXXX
```

Replace the variable names with the credentials of the mongo database you want to use.

## Scraper

Since it uses selenium, you need to install the driver for your browser. To do that, you can follow the instructions on the [Selenium documentation](https://selenium-python.readthedocs.io/installation.html#drivers).

The script is using `Chrome`, but you can use any other browser by changing the driver initialization code.

Once you've downloaded the driver, add the folder where it is located to your `PATH` environment variable.

The scraper can run mutiple scraper instances, and every time one of the scrapers collects information about a city, that city will be tagged as `scraped`.
That way, the other scrapers can skip the cities that have already been scraped.

Whenever an instance crashes for whatever reason, it will be restarted automatically.

To run the scraper, execute the following command:

```
python main.py
```

You can run the command with the '-h' flag to see the available options.

```
options:
  -h, --help           show this help message and exit
  --threads THREADS    Number of threads to run (default: 1)
  --country COUNTRY    Country to scrape (default: it will scrape all countries)
  --priority PRIORITY  Scrape countries with specified priority (default: it will scrape all countries)
  --chunck CHUNCK      Chunck size fetch from all three collections on the db. (default: 100 => 100 * 3 = 300)
```
