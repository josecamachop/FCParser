#!/usr/bin/env python

"""
parser -- Program for parsing and processing raw network
data and preparing it for further multivariate analysis using
FaaC parser library.


Authors:    Manuel Jurado Vazquez (manjurvaz@ugr.es) 
            Jose Manuel Garcia Gimenez (jgarciag@ugr.es) 
            Alejandro Perez Villegas (alextoni@gmail.com)
            Jose Camacho (josecamacho@ugr.es)
         
Last Modification: 27/May/2021

"""
import multiprocessing as mp
import argparse
import os
import gzip
import re
import time
from operator import add
import faac
import math
from collections import OrderedDict
from math import floor
from sys import version_info
#import datetime
#import subprocess
#import copy    


def main(call='external',configfile=''):

    startTime = time.time()

    # if called from terminal
    # if not, the parser must be called in this way: parser.main(call='internal',configfile='<route_to_config_file>')
    if call == 'external':
        args = getArguments()
        configfile = args.config
        global debugmode; debugmode = args.debug    # debugmode defined as global as it will be used in many functions

    # Get configuration
    print("LOADING GENERAL CONFIGURATION FILE...")
    parserConfig = faac.getConfiguration(configfile)
    config = faac.loadConfig(parserConfig, 'fcparser', debugmode)
    
    # Print configuration summary
    configSummary(config)

    # Output Weights
    outputWeight(config)
    
    # Create stats file and count data entries
    stats = create_stats(config)
    stats = count_entries(config,stats)

    # processing files. Online mode
    if parserConfig['Online']:
        data = online_parsing(config)
        output_data = fuseObs_online(data)

    # process offline 
    else:
        if debugmode:
            faac.debugProgram('fcparser.init_message', [])
            global user_input; user_input = None   # Global variable storing user input command
        else:
            print('\033[33m'+ "Note: Malformed logs or inaccurate data source configuration files will result in None variables which will not be counted in any feature.")
            print("Run program in debug mode with -d option to check how the records are parsed." +'\033[m')
        
        data = offline_parsing(config, startTime, stats)
        output_data = fuseObs_offline(data)
        #with open(config['OUTDIR']+'fused_dict', 'w') as f: print(output_data, file=f) # this output file does not seem to be relevant for the user
        
    # write in stats file
    write_stats(config, stats)

    # Output results
    write_output(output_data, config)
    
    print("Elapsed: %s \n" %(prettyTime(time.time() - startTime))) 



def offline_parsing(config,startTime,stats):
    '''
    Main process for offline parsing. In this case, the program is in charge of temporal sampling.
    Also, it is multiprocess for processing large files faster. Number of cores used and chunk sizes
    to divide files for the different processes. 
    '''
    results = {}

    for source in config['SOURCES']:
        results[source] = []
        currentTime = time.time()
        if not debugmode:
            print("\n-----------------------------------------------------------------------\n")
            print("Elapsed: %s \n" %(prettyTime(currentTime - startTime)))    
            
        results[source] = process_multifile(config, source, stats) 


    return results


def process_multifile(config, source, stats):
    '''
    processing files procedure for sources in offline parsing. In this function the pool 
    of proccesses is created. Each file is fragmented in chunk sizes that can be load to memory. 
    Each process is assigned a chunk of file to be processed.
    The results of each process are gathered to be postprocessed. 
    '''
    results = {}
    count = 0
    lengths = stats['sizes'][source] #filesize

    for i in range(len(config['SOURCES'][source]['FILES'])):
        input_path = config['SOURCES'][source]['FILES'][i]
        if input_path:
            count += 1
            tag = getTag(input_path)
            cont = True
            init = 0
            remain = lengths[i]     
            
            #Print some progress stats
            if not debugmode:   
                print("%s  #%s / %s  %s" %(source, str(count), str(len(config['SOURCES'][source]['FILES'])), tag))
            else:
                faac.debugProgram('fcparser.process_multifile.source', [source, stats['lines'][source]])

            # Recalculate Ncores if nlogs < ncores for this datasource
            ncores_bkp = config['Cores']
            nlogs = stats['lines'][source]
            if config['Cores']>1 and 10*config['Cores'] > nlogs:     
                config['Cores'] = max(1, floor(nlogs/10))
            
            # Multiprocessing
            pool = mp.Pool(config['Cores'])
            while cont:                          # cleans memory from processes
                jobs = list()
                # Initially, data is split into chunks with size: min(filesize, max_chunk) / Ncores
                for fragStart,fragSize in frag(input_path,init,config['RECORD_SEPARATOR'][source], int(math.ceil(float(min(remain,config['Csize']))/config['Cores'])), config['Csize']):
                    if not debugmode:
                        jobs.append( pool.apply_async(process_file,[input_path,fragStart,fragSize,config, source, stats]) )
                    else:
                        stats['processed_lines'][source], obsDict = process_file(input_path,fragStart,fragSize,config,source,stats)
                        
                else:
                    if fragStart+fragSize < lengths[i]:
                        remain = lengths[i] - fragStart+fragSize
                        init = fragStart+fragSize 
                    else:
                        if not debugmode:
                            cont = False
                        else:
                            print('\033[33m'+ "* End of file %s *" %(input_path) +'\033[m')
                            print("Loading file again...")
                            init=0
                            stats['processed_lines'][source] = 0  # reset lines
                            remain = lengths[i] 
                            global user_input; user_input = None

                            
                for job in jobs:
                    job_data = job.get()
                    processed_lines = job_data[0]
                    obsDict = job_data[1]
                    stats['processed_lines'][source] += processed_lines
                    results = combine(results,obsDict)
                    
            
            pool.close()
            config['Cores'] = ncores_bkp

    return results 

def combine(results, obsDict):
    '''
    Function to combine the outputs of the several processes
    '''        
    for key in obsDict:
        if key in results:
            results[key].aggregate(obsDict[key])
        else:
            results[key] = obsDict[key]
    
    return results 
            
def process_file(file, fragStart, fragSize, config, source, stats):
    '''
    Function that uses each process to get data entries from  data using the separator defined
    in configuration files that will be transformed into observations. This is used only in offline parsing. 
    '''
    obsDict = {}
    processed_lines = 0
    separator = config['RECORD_SEPARATOR'][source]
    
    if debugmode:
        processed_lines = stats['processed_lines'][source]
        global opmode
        global user_input
        if user_input:
            read_input = False
        else:
            read_input = True

    try:    
        if file.endswith('.gz'):                    
            f = gzip.open(file, 'r', newline="")
        else:
            f = open(file, 'r', newline="")

        f.seek(fragStart)
        lines = f.read(fragSize)
        #if debugmode: print("[Loaded set of %d logs]\n" %(len(lines.split(separator))))
            
    finally:
        f.close()
        
   
    for line in iter_split(lines, separator):  

        if debugmode:
            if read_input:
                opmode, user_input = faac.debugProgram('fcparser.user_input', [processed_lines+1])
                
            if (opmode=='enter') or (opmode=='goline' and user_input==(processed_lines+1)) or (opmode=='searchstr' and user_input in line):
                faac.debugProgram('fcparser.process_file.line', [processed_lines+1, line])
                read_input = True        # after a match, will process line and read user input again
                user_input = None        # Reset user_input after a match
            else:
                processed_lines+=1       # skip processing this log entry because no match
                read_input = False
                continue
                
        tag, obs = process_log(line, config, source)
        if tag == 0:
            tag = file.split("/")[-1]

        if debugmode:
            processed_lines+=1 
        elif obs is not None:
            add_observation(obsDict, obs, tag)
            processed_lines+=1
    
    #if debugmode: print('\033[33m'+ "End of file chunk. Loading next chunk..." +'\033[m')

    return processed_lines, obsDict


def process_log(log,config, source):
    '''
    Function take on data entry as input an transform it into a preliminary observation
    '''     

    ignore_log = 0      # flag to skip processing this log
    if not log or not log.strip():  
        ignore_log=1    # do not process empty logs or containing only spaces
        print('\033[31m'+ "The entry log is empty and will not be processed\n" +'\033[m')

    if not ignore_log:
        record = faac.Record(log,config['SOURCES'][source]['CONFIG']['VARIABLES'], config['STRUCTURED'][source], config['TSFORMAT'][source], config['All'])
        if debugmode: faac.debugProgram('fcparser.process_log.record', [record])
        
        obs = faac.Observation.fromRecord(record, config['FEATURES'][source])
        if debugmode: faac.debugProgram('fcparser.process_log.observation', [obs])
        
        timearg = config['TIMEARG'][source] # name of variable which contains timestamp 
        log_timestamp = record.variables[timearg][0].value
    
        # Check if log_timestamp will be considered according to time sampling parameters
        if 'start' in config['Time']:
            if log_timestamp < config['Time']['start']:
                ignore_log = 1
        if 'end' in config['Time']:
            if log_timestamp > config['Time']['end']:
                ignore_log = 1 
    
    if not ignore_log:
        window = config['Time']['window']            
        try:
            if config['Keys']:
                tag = list()
                tag2 = normalize_timestamps(log_timestamp, window)
                tag.append(tag2.strftime("%Y%m%d%H%M"))
                for i in range(len(config['Keys'])):
                    if len(record.variables[config['Keys'][i]]) > 0:
                        tag.append(str(record.variables[config['Keys'][i]][0]))    # Careful!, only works (intentionally) for the first instance of a variable in a record
                if len(tag) > 1:
                    tag = tuple(tag)
                else:
                    tag = tag[0]        
            else:
                tag2 = normalize_timestamps(log_timestamp, window)
                tag = tag2.strftime("%Y%m%d%H%M")

        except: 
            # Exception as err
            #print("[!] Log failed. Reason: "+ (str(err) + "\nLog entry: " + repr(log[:300])+ "\nRecord value: "+ str(record)))
            tag, obs = None, None
            if debugmode:
                print('\033[31m'+ "This entry log would be ignored due to errors" +'\033[m')
    
    else:
        tag, obs = None, None
        
    return tag, obs
    

def normalize_timestamps(t, window):
    '''
    Function that transform timestamps of data entries to a normalized format. It also do the 
    time sampling using the time window defined in the configuration file.
    '''    
    #try:
    if window == 0:
        return 0
    if window <= 60:
        new_minute = t.minute - t.minute % window  
        t = t.replace(minute = new_minute, second = 0)
    elif window <= 1440:
        window_m = window % 60  # for simplicity, if window > 60 we only use the hours
        window_h = int((window - window_m) / 60)
        new_hour = t.hour - t.hour % window_h  
        t = t.replace(hour = new_hour, minute = 0, second = 0)                 
    return t
    #except Exception as err: print("[!] Normalizing error: "+str(err))
        
    return 0


def frag(fname, init, separator, size, max_chunk):
    '''
    Function to fragment files in chunks to be parallel processed for structured files by lines
    '''
    #print ("File pos: %d, size: %d, max_chunk: %d", init, size, max_chunk)
    
    try:
        if fname.endswith('.gz'):                    
            f = gzip.open(fname, 'r', newline="")
        else:
            f = open(fname, 'r', newline="")


        f.seek(init)
        end = f.tell()
        init = end
        separator_size = len(separator)
        while end-init < max_chunk:
            start = end
            tmp = f.read(size)
            i = tmp.rfind(separator)
            if i == -1:
                yield start, len(tmp)
                break
            f.seek(start+i+separator_size)
            end = f.tell()
            #print("Frag: "+str([start, i, end]))

            yield start, end-start

    finally:
        f.close()
        
        
def fuseObs_offline(resultado):
    '''
    Sources Fusion in a single stream. 
    '''

    v = list(resultado.keys())
    fused_res = resultado[v[0]]


    for source in v[1:]:

        # Get len of data vector in observation object from that source
        arbitrary_len2 = len(next(iter(list(resultado[source].values()))).data)
        try:
            arbitrary_len = len(next(iter(list(fused_res.values()))).data)
        except:
            arbitrary_len = 0

        for date in resultado[source]:

            if date not in fused_res:
                fused_res[date] = resultado[source][date]
                # add zero observation vector before
                fused_res[date].zeroPadding(arbitrary_len, position=-1)
            else:
                fused_res[date].fuse(resultado[source][date].data) 
                
                
        for date2 in fused_res:

            if date2 not in resultado[source]:
                # add zero observation vector after
                fused_res[date2].zeroPadding(arbitrary_len2, position=0)
                #fused_res[date2].fuse([0]*arbitrary_len2) # old implementation (master branch)

    return fused_res


def iter_split(line, delimiter):
    start = 0
    line_size = len(line)
    delimiter_size = len(delimiter)
    while start<line_size:
        end = line.find(delimiter, start)
        yield line[start:end]
        if end == -1: break
        start = end + delimiter_size


def add_observation(obsDict,obs,tag):
    '''
    Adds an observation (obs) to dictionary (obsDict) in an entry (tag) 
    '''
    if tag in list(obsDict.keys()):
        obsDict[tag].aggregate(obs)
    else:
        obsDict[tag] = obs
    

def getTag(filename):
    '''
    function to identify data source by the input file
    '''
    tagSearch = re.search("(\w*)\.\w*$", filename)
    if tagSearch:
        return tagSearch.group(1)
    else:
        return None


def file_len(fname):
    '''
    Function to get lines from a file
    '''
    count_log = 0
    try:
        if fname.endswith('.gz'):
            input_file = gzip.open(fname,'r')
        else:
            input_file = open(fname,'r')

        for count_log, l in enumerate(input_file):
            pass

    finally:
        size = input_file.tell()
        input_file.close()

    return count_log+1,size


def file_uns_len(fname, separator):
    '''
    Function determine de number of logs for a unstructured file 
    '''
    count_log = 0
    try:
        if fname.endswith('.gz'):
            input_file = gzip.open(fname,'r')
        else:
            input_file = open(fname,'r')
        
        log ="" 
        for line in input_file:        
            log += line 

            splitt = log.split(separator);
            if len(splitt) > 1:
                count_log += 1    
                log = log[len(splitt[0])+1:]
        
        if not log or not log.strip():
            pass
        else: 
            count_log+=1    # count last log when it is not empty or containing spaces only

    finally:
        size = input_file.tell()
        input_file.close()

    return count_log,size    


def create_stats(config):
    '''
    Legacy function - To be updated
    '''
    stats = {}
    statsPath = config['OUTDIR'] + config['OUTSTATS']
    if not debugmode:
        statsStream = open(statsPath, 'w')
        statsStream.write("STATS\n")
        statsStream.write("=================================================\n\n\n")
        statsStream.close()
    stats['statsPath'] = statsPath

    return stats


def count_entries(config,stats):
    '''
    Function to get the amount of data entries and bytes for each data source
    '''

    lines = {}
    stats['processed_lines'] = {}
    stats['sizes'] = {}
    for source in config['SOURCES']:
        lines[source] = 0
        stats['processed_lines'][source] = 0
        stats['sizes'][source] = list()
        for file in config['SOURCES'][source]['FILES']:
            
            if config['STRUCTURED'][source]:
                (l,s) = file_len(file)
                lines[source] += l
                stats['sizes'][source].append(s)
                
            # unstructured source
            else:
                (l,s) = file_uns_len(file,config['RECORD_SEPARATOR'][source])
                lines[source] += l
                stats['sizes'][source].append(s)

    # Sum lines from all datasources to obtain total lines.
    total_lines = 0

    stats['lines'] = {}
    for source in lines:
        total_lines += lines[source]
        stats['lines'][source] = lines[source]

    stats['total_lines'] = total_lines
    
    
    return stats            
    

def prettyTime(elapsed):
    '''
    Function to format time for print.
    '''
    hours = int(elapsed // 3600)
    minutes = int(elapsed // 60 % 60)
    seconds = int(elapsed % 60)
    pretty = str(seconds) + " secs"
    if minutes or hours:
        pretty = str(minutes) + " mins, " + pretty
    if hours:
        pretty = str(hours) + " hours, " + pretty
    return pretty


def getArguments():
    '''
    Function to get input arguments from configuration file
    '''
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description='''Multivariate Analysis Parsing Tool.''')
    parser.add_argument('config', metavar='CONFIG', help='Parser Configuration File.')
    parser.add_argument('-d', '-g', '--debug', action='store_true', help="Run fcparser in debug mode")
    args = parser.parse_args()
    return args


def configSummary(config):
    '''
    Print a summary of loaded parameters
    '''

    print("-----------------------------------------------------------------------")
    print("Data Sources:")
    for source in config['SOURCES']:
        print(" * %s %s variables   %s features" %((source).ljust(18), str(len(config['SOURCES'][source]['CONFIG']['VARIABLES'])).ljust(2), str(len(config['SOURCES'][source]['CONFIG']['FEATURES'])).ljust(3)))
    print(" TOTAL %s features" %(str(sum(len(l) for l in config['FEATURES'].values()))))
    print()
    
    if not debugmode:
        print("Output:")
        print("  Directory: %s" %(config['OUTDIR']))
        print("  Stats file: %s" %(config['OUTSTATS']))
        print("  Weights file: %s" %(config['OUTW']))

    print("-----------------------------------------------------------------------\n")
    
    
def outputWeight(config):
    '''
    Generate output file with the weights assigned to each feature.
    '''
    weightsPath = config['OUTDIR'] + config['OUTW']
    if not debugmode:
        weightsStream = open(weightsPath, 'w')
        weightsStream.write(', '.join(config['features']) + '\n')
        weightsStream.write(', '.join(config['weights']) + '\n')
        weightsStream.close()
    

def write_stats(config,stats):
    
    statsStream = open(stats['statsPath'], 'a')

    for source in config['SOURCES']:
        statsStream.write( " * %s \n" %((source).ljust(18)))
        statsStream.write( "\t\t %s variables \n" %(len(config['SOURCES'][source]['CONFIG']['VARIABLES'])))
        statsStream.write( "\t\t %s features \n" %(len(config['SOURCES'][source]['CONFIG']['FEATURES'])))
        statsStream.write( "\t\t %d logs - %d processed logs \n" %(stats['lines'][source], stats['processed_lines'][source]))
        statsStream.write( "\t\t %d total bytes (%.2f MB) \n\n" %(sum(stats['sizes'][source]),
                                                           (sum(stats['sizes'][source]))*1e-6))

    statsStream.write("\n=================================================\n\n")

    statsStream.close()


def write_output(output, config):
    '''Write parsing ouput into a file, for each timestamp a file is written
    If the FCParser is mode online, only one file is written as output.
    Furthermore, an adition file with a list of the features is ouputted.
    '''

    features = []
    for source in config['SOURCES']:
        for feat in config['SOURCES'][source]['CONFIG']['FEATURES']:
            features.append(feat['name'])

    with open(config['OUTDIR'] + 'headers.dat', 'w') as f:
        f.write(str(features))

    if isinstance(output, dict):
        
        # List of files, one for each timestamp
        lfiles = list();
        for k in output:
            if isinstance(k, tuple):
                tag = k[0]
            else:
                tag = k
                
            if tag not in lfiles:
                lfiles.append(tag)
                
        if config['Incremental']:
            for i in range(len(lfiles)):
                
                tagt = lfiles[i]
                fname = config['OUTDIR'] + 'output-'+ tagt + '.dat'
                if os.path.isfile(fname):
                    with open(fname, 'r') as f:

                        for line in f:

                            if line.find(':')==-1:
                                obs_aux = line
                                tag = tagt

                            else:
                                laux = line.rsplit(': ',2)
                                tag = [tagt]

                                tagso =  laux[0].split(',')
                                list(map(str.strip,tagso))
                                for j in range(len(tagso)):
                                    tag.append(tagso[j])

                                obs_aux = laux[1]
                                tag = tuple(tag)

                            obs = obs_aux.split(',')

                            try:
                                for j in range(len(obs)):
                                    obs[j] = int(obs[j])
                            except:
                                obs = []

                            if tag in output:
                                for j in range(len(obs)):
                                    output[tag].data[j].value += obs[j]
                            else:
                                j = 0;
                                data = []
                                for source in config['SOURCES']:
                                    for feat in config['SOURCES'][source]['CONFIG']['FEATURES']:
                                        data.append(faac.Feature(feat))
                                        data[j].value += obs[j]
                                        j += 1

                                output[tag] = faac.Observation(data)
                
                    open(fname, 'w').close()


        l = OrderedDict(sorted(output.items()))
        for k in list(l.keys()):
            if isinstance(k, tuple):
                tag = k[0]
            else:
                tag = k
                
            fname = config['OUTDIR'] + 'output-'+ tag + '.dat'
            with open(fname, 'a') as f:
                if isinstance(k, tuple):
                    tag2 = list(map(str.strip,k[1:]))
                    f.write(','.join(tag2)+': ')
                
                f.write(','.join(map(str,output[k].data))+ '\n')
    else:
        with open(config['OUTDIR'] + 'output.dat' , 'w') as f:
            f.write(','.join(map(str,output.data)))
            
            
def online_parsing(config):
    '''
    Main process for online parsing. In this case, the program generates one output for the 
    the input file, wich means, no time splitting. Online parsing is designed to be integrated
    in other program with would be in charge of the input management. 
    '''
    results = {}

    for source in config['SOURCES']:
        obsDict = obsDict_online()
        
        # If structured datasource
        if config['SOURCES'][source]['CONFIG']['structured']:
            for fname in config['SOURCES'][source]['FILES']:

                try:
    
                    if fname.endswith('.gz'):                    
                        f = gzip.open(fname, 'r')
                    else:
                        f = open(fname, 'r')
                
                    lines = f.readlines()
                    for line in lines:
                        tag, obs = process_log(line,config,source)
                        obsDict.add(obs)
                finally:
                    f.close()
        else:
            separator = config['RECORD_SEPARATOR'][source]
            for fname in config['SOURCES'][source]['FILES']:

                try:
    
                    if fname.endswith('.gz'):                    
                        f = gzip.open(fname, 'r')
                    else:
                        f = open(fname, 'r')

                    lines = f.read()
                    log = ''
                    for line in lines:
                        log += line 
                        if separator in log:
                            tag, obs = process_log(log,config, source)
                            obsDict.add(obs)
                            log = ''    

                    tag, obs = process_log(log,config, source)
                    obsDict.add(obs)

                finally:
                    f.close()

        results[source] = obsDict
    return results


def fuseObs_online(resultado):
    '''
    Function to fuse all the results obtained from all the processes to form a single observation in 
    array form.
    '''
    fused_res = []
    #features = []

    for source in resultado:

        fused_res = fused_res + resultado[source].obsList

    return fused_res

    
class obsDict_online(object):
    """
    Class to store observations of parsed data in online  mode. This class include 
    methods to add new partial observation to an absolute observation and a other 
    method for visual representation.
    """
    def __init__(self):
        self.obsList = []

    def add(self,obs):
        if self.obsList:
            self.obsList = list(map(add, obs, self.obsList)) # won't work in new code
        else:
            self.obsList = obs

    def printt(self):
        print(self.obsList)


if __name__ == "__main__":
    
    if version_info[0] != 3:
        print('\033[31m'+ "** PYTHON VERSION ERROR **" +'\033[m')
        print("Please, use python3 to run this program")
        exit(1)
        
    main()
