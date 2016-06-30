"""Movie-meta

Meta movie allows one to generate movie meta based on contents of directory.
Generates movie params from available IMDB API and helps you sort movie based
on ratings, genere, title etc.

@TODO:
    1. Automated duplicacy detection.
    2. Path watch module. Generate meta whenever new content in existing dir
    is added.
    3. Movie suggestions based on most viewed movie by current user.
    4. skip processed ones (cache)
"""
import os,sys,time
import json
import requests
import logging
from guessit import guessit
from threading import Thread
from Queue import Queue
from argparse import ArgumentParser

class Threader:
    """Threader class.

    Threader class is responsible for making multiple parallel requests
    """
    
    def __init__(self, num_threads=5):
        self.concurrent = num_threads
        self.queue = Queue(num_threads * 2)
        self.obj = None

    def attach(self, obj):
        self.obj = obj

    def job(self):
        while True:
            url = self.queue.get()
            if self.obj is not None:
                response = self.obj.worker(url)
                self.result(response)
            self.queue.task_done()

    def result(self,response):
        try:
            self.obj.result(response)
        except Exception:
            print "Exception occured"

    def start(self):
        for i in range(self.concurrent):
            t = Thread(target=self.job)
            t.daemon = True
            t.start()

    def submit(self):
        try:
            self.obj.prepare(self.queue)
        except KeyboardInterrupt:
            sys.exit(1)
        

class MovieMeta:
    """MovieMeta class.

    MovieMeta class is the main entry point for the whole program.
    It is responsible for getting api response, as well as generating
    sort table.
    """

    def __init__(self, current_dir="", log=False):
        
        self.currentDir = current_dir
        
        #Constants
        self.SUBDIR_SEP = ","
        self.SUBDIR_FILE = "subdir.txt"
        self.URL_TITLE = 'http://www.omdbapi.com/?t={0}'
        self.URL_TITLE_YEAR = 'http://www.omdbapi.com/?t={0}&y={1}'
        

        #Arrays and stuffs
        self.movieJsonArr = []
        self.movieArr = []
        self.imdbJSON = []
        self.subdirs = []
        self.makelog = log
        self.logger = None
        self.start_time = 0

        #Init stuff
        self._processed = False
        if len(self.currentDir) == 0:
            self.currentDir = os.getcwd()
        subdir = ''
        if os.path.isfile(self.SUBDIR_FILE):
            with open(self.SUBDIR_FILE) as f:subdir = f.readline()
        self.subdir(subdir)

        self.debug(log)

    def subdir(self, subdirs = ""):
        self.subdirs = str(subdirs).split(self.SUBDIR_SEP)

    def debug(self, log):
        self.makelog = log
        if log:
            FORMAT = '%(asctime)-8s %(levelname)s : %(message)s'
            self.logger = logging.getLogger("moviemeta")
            logging.basicConfig(filename='moviemeta.log',level=logging.DEBUG,format=FORMAT)

    def makeJSON (self):
        for movieObj in self.movieArr:
            mov = {}
            mov["title"] = movieObj.get("title") if movieObj.get("title") is not None else None
            mov["year"] = movieObj.get("year") if movieObj.get("year") is not None else None
            self.movieJsonArr.append(mov)

        self.movieJSON = json.dumps(self.movieJsonArr)
        self._processed = True

        if self.makelog:
            self.logger.info('Finished local directory parsing...')
            
        return self.movieJSON
        

    def _walk(self,top):
        """ Our custom walker , see os.walk()"""
        try:
            names = os.listdir(top)
        except os.error:
            return
        
        for name in names:
            if self.subdirs.count(name) > 0:
                name = os.path.join(top, name)
                if os.path.isdir(name):
                    self._walk(name)
            else:
                self.movieArr.append( guessit(name) )

    def _process(self):
        #only proceed if request is not already honored
        if not self._processed:
            if self.makelog:
                self.logger.info('Starting local directory parsing...')
            self._walk( current_dir )
            self.makeJSON()

    def get(self,json=False):
        self._process()
        return self.movieJSON if json else self.movieJsonArr

    def writeFile(self,filename="moviemeta.txt"):
        f = open(filename, "w")
        f.write(json.dumps(self.imdbJSON))
        f.close()

    def getResult(self):
        return json.dumps(self.imdbJSON)

    def prepare(self,queue):
        movies = self.get()
        for movie in movies:
            url = self.getURL(movie)
            queue.put({'title':movie["title"],'url':url})
        queue.join()

    def result(self,response):
        self.imdbJSON.append(response)

    def worker(self,obj):
        if self.makelog:
            self.logger.info('Fetching movie data: %s...', obj['title'])
        try:
            fetchedDetails = requests.get(obj['url'])
            details = fetchedDetails.content
            movieJSON = self.parseIMDBResponse( obj['title'], json.loads(details) )
            return movieJSON            

        #catch timeouts and report    
        except requests.exceptions.Timeout:
            if self.makelog:
                self.logger.warning('Error fetching movie data: %s [ERR_TIMEOUT]', obj['title'])
            return {"Response":False,"Error":"err_timeout"}
                
        #catch connection breaks and report       
        except requests.exceptions.ConnectionError:
            if self.makelog:
                self.logger.warning('Error fetching movie data: %s [ERR_CONNECT]', obj['title'])
            return {"Response":False,"Error":"err_connect"}

    def getURL(self,movie):
        url = "" 
        if movie["title"] is not None:
            url = self.URL_TITLE.format(movie["title"])

        if movie["year"] is not None:
            url = self.URL_TITLE_YEAR.format(movie["title"],movie["year"])
        return url

    def getIMDB(self, jsonify = True):

        self.start_time = time.time()
        self._process()
            
        if not self.movieJsonArr:
            if self.makelog:
                self.logger.info('No movies to fetch')
            return

        for movie in self.movieJsonArr:
            url = self.getURL(movie)
            movieJSON = self.worker({'title':movie["title"],'url':url})
            self.imdbJSON.append(movieJSON)

        end_time = time.time() - self.start_time
        if self.makelog:
            self.logger.info('All data fetched in %.3f s', end_time)
        self.start_time = 0

        return json.dumps(self.imdbJSON) if jsonify else self.imdbJSON

    def parseIMDBResponse( self, title, resp ):
        IMDBResp = {}
        IMDBResp["movieTitle"] = title
        IMDBResp["movieYear"] = ''
        IMDBResp["movieRuntime"] = ''
        IMDBResp["movieGenre"] = ''
        IMDBResp["moviePlot"] = ''
        IMDBResp["movieMeta"] = ''
        IMDBResp["movieImdb"] = ''
        IMDBResp["movieAwards"] = ''
        
        if resp['Response'] == "False":
            #report to error log
            return IMDBResp

        if resp['Title']:
            IMDBResp["movieTitle"] = resp['Title'].encode('utf-8').replace('"','\\"')
        if resp['Year']:
            IMDBResp["movieYear"] = resp['Year'].encode('utf-8').replace('"','\\"')
        if (resp['Runtime']):
            IMDBResp["movieRuntime"] = "" if resp['Runtime'] == "N/A" else resp['Runtime'].encode('utf-8').replace('"','\\"')
        if resp['Genre']:
            IMDBResp["movieGenre"] = resp['Genre'].encode('utf-8').replace('"','\\"')
        if resp['Plot']:
            IMDBResp["moviePlot"] = resp['Plot'].encode('utf-8').replace('"','\\"')
        if resp['Metascore'] == "N/A":
            IMDBResp["movieMeta"] = 0
        elif resp['Metascore']:
            IMDBResp["movieMeta"] = resp['Metascore'].encode('utf-8').replace('"','\\"')
        if resp['imdbRating']:
            IMDBResp["movieImdb"] = 0 if resp['imdbRating'] == "N/A" else resp['imdbRating'].encode('utf-8').replace('"','\\"')
        if resp['Awards']:
            IMDBResp["movieAwards"] = resp['Awards'].encode('utf-8').replace('"','\\"')

        return IMDBResp

if __name__ == "__main__":

    #Check if external arguments are passed
    parser = ArgumentParser(description='Movie meta generator')
    parser.add_argument("-d", help="Directory path")
    parser.add_argument("--log", action='store_true', help="log behaviour")
    parser.add_argument("-s", action='store_true', help="Use in sequential mode")
    args = parser.parse_args()

    current_dir = ""
    if getattr(args, 'd') is not None:
        current_dir = str(getattr(args, 'd'))

    sequential = getattr(args, 's')

    #create a MovieMeta object to get movies from mentioned directory
    movies = MovieMeta( current_dir )

    #Use logger? (True/False)
    movies.debug(getattr(args, 'log'))

    if sequential:
        """
        This method makes requests serially
        """
        movies.getIMDB()
    else:
        """
        use this method to make parallel requests.
        5 concurrent requests are enough. Make it more if you have
        really large movie collection in single directory.
        
        Optionally, you can go into multicore CPU pooling,
        but its not really required here.
        """
        start_time = time.time()
        
        threader = Threader(5)
        threader.attach(movies)
        threader.start()
        threader.submit()

        #Measure your elapsed time after all threads finished execution
        end_time = time.time() - start_time
        print "Finished in %.3f s" % end_time

    
    #Write the JSON string to file
    movies.writeFile()

    
    """At this point, you should have required JSON"""
    #print movies.getResult()

