Instructions
============
Installation
------------
This project is made up of just a few files:

1. In the objs folder there are two files that contain classes to help
interact with Websites for the word-count portion of the code challenge
and a class to interact with pulling data from the Alexa Top Sites
API.

2. In the top level folder there are few scripts that run the code
challenge in slightly different ways.

    - The top-sites.py file runs the website queries in parallel
    and results in a much shorter time just gathering the home page
    data of each website.
    - The top-sites-orig.py file runs all the website queries serially
    which proves to be a little more reliable but quite a bit slower

I just wanted to show different ways this process could be written and
really was just an easy way for me to keep things separate as I tried
different ideas and just decided to keep them both.


There are few libraries that need to be installed through pip. It makes
sense to run this with a virtualenv to keep things separate. I have been
unable to get that working on this laptop due to some issues with
virtualenv permissions that I have not been able to get figured out.
I have included a requirements.txt file to help install the needed libraries.

    pip install -f requirements.txt

Run Instructions
----------------
Each python script can be run by calling

    python top-sites.py
    python top-sites-pool.py

They can also be run by just executing them directly

    ./top-sites.py
    ./top-sites-pool.py

#### Command line arguments ###
* --access-key-id <i>your AWS access key ID </i>
* --secret-access-key <i>your AWS secret access key </i>
* --local-file /Users/myoung/Downloads/top_sites_raw.xml
* --s3-location s3://myoung-alexa-site-data/top_sites_raw.xml
* --worker-processes 10

* Access Key Id (--access-key-id)
    - Your AWS access key ID. This is used to interact with AWS.
    The calls to AWS include any calls to download the top sites
    XML file from S3 or the call to the Alexa Top Sites API to
    get the XML directly.
    - This can also be defined in your environment variables as
    AWS_ACCESS_KEY_ID
* Secret Access Key (--secret-access-key)
    - Your AWS secret access key. This is used to interact with AWS.
    The calls to AWS include any calls to download the top sites
    XML file from S3 or the call to the Alexa Top Sites API to
    get the XML directly.
    - This can also be defined in your environment variables as
    AWS_SECRET_ACCESS_KEY
* Local File Location (--local-file)
    - The location of the top sites raw XML file from your local computer.
    It turns out it is fairly expensive to query the API so this is
    a way to just provide the file locally.
    - This option takes precedence
    over the S3 option if they are both passed in.
* S3 File Location (--s3-location)
    - The location of the raw XML file from an S3 location. This can
    take either the URL form to the S3 file or an S3 formatted location.
    This will use your AWS keys to try and download the file.
* Worker Processes (--worker-processes)
    - The number of local process to spawn to run the map-reduce
    calculations and to run the pool of URL fetchers.
    - Defaults to 4.

If neither a local file or S3 file are specified, a new request will
be made to the Alexa top 100 sites API.

Output
------
The output of this program could use more time. Right now it spits
out data within stdout on the screen in the command-line. There is
a simple timing decorator used to do a basic and inaccurate timing
on the methods you guys asked for run-time on. Those are produced
whenever the method call is complete and so will be embedded in the
normal output logs as well.

The final command is to output some stats from the cProfile module.
This seems to quite quite a lot of information and finding the
relevant information to show was a little difficult, but it provides
good overall timing and decent timing for total time consumed by
the major function calls in the script.

Ideally this output would be formatted nicely and probably dumped
to a specified output file.

Future Enhancements
-------------------
I wanted to put down some thoughts on how this script could be made
better, but that would require more time from me to learn.

* Output Files
    - Like I mentioned in the output section I would like to make
    this output more readable.
    - The output should be dumped to a file instead of just using
    the loggers and stdout.
    - There is probably a data format that should be used that would
    allow for comparison runs to be made.
    - There is a lot of variance based on connecting to the websites.
    I think it may make more sense to store that raw info in a DB and
    have the program read from that to get a better idea on how the techniques
    compare.
* AWS Usage
    - I think these calls fit perfectly into a serverless architecture.
    A lambda function could be used to
        - Run the web call, store the data in Dynamodb or other DB
        - Run the map-reduce word count for each site
        - Query the DB and do the average word count
        - Query the DB and rank the headers
    - Serverless is something I would like to concentrate on learning
    how to actually use. I was not able to get external libraries to
    install correctly on Lambda and wanted to get something to you
    guys instead of spending time learning how to do that correctly first.
    - I think the challenge with a serverless approach would be keeping
    track of when lambda jobs are complete before running analysis
    over all the collected data.
* Hadoop
    - The map-reduce nature of these scripts also lends itself to running
    the analysis as a hadoop job.
    - This would also make the code much more scalable as you could ingest
    a file containing the top million sites and just send it through an
    EMR cluster and spit out the files into S3.
    - Again this would take time for me to learn how to actually write
    a Hadoop job.
* Website Parsing
    - I decided to use BeautifulSoup and the built-in HTML parser
    to parse the homepage of these sites. Mostly because I was familiar
    and because it seemed to be a common suggestion.
    - There is some logic in the code to pull out content that would not
    be visible to users, but there is still quite a bit of work that could
    be done to make it better.
    - There are many sites that mostly consist of javascript and therefore
    to do not represent what the user actually sees.
    - There may be a better lib for parsing the sites.
    - It may be better to attempt to run the call to the homepage through
    a headless browser or something that actually renders the site.
