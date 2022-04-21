# Setting up database

Make sure to be using these settings in the database and all the tables created inside of it:

-   Charset: utf8mb4
-   Collation: utf8mb4_unicode_ci

Once that's done, dump the data in the following order:

-   `paises.sql`
-   `departamentos.sql`
-   `ciudades.sql`

Using the command:

```
SOURCE PATH\TO\FILE\dump.sql
```

# Scraper

To configure the mysql database, create a `.env` file with the following content:

```
    DB_HOST=XXXXXXXXXX
    DB_USER=XXXXXXXXXX
    DB_PASSWORD=XXXXXXXXXX
    DB_NAME=XXXXXXXXXX
```

The scraper can run mutiple scraper instances, and every time one of the scrapers collects information about a city, the id of city will be stored in the file `cached.json`. That way, the other scrapers can skip the cities that have already been scraped.

Whenever an instance crashes for whatever reason, it will be restarted automatically.

To run the scraper, run the following command:

```
    python main.py {thread_count}
```

Where thread_count is the number of threads (instances) that will be used to scrape the data.
When no thread_count is specified, the default value is 1.
