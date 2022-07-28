#!/usr/bin/env python

"""
learner -- Program for automatically learning features from the set of variables
of raw network data using the FaaC parser library.


Authors:    Jose Camacho (josecamacho@ugr.es)
            Manuel Jurado Vazquez (manjurvaz@ugr.es) 
         
Last Modification: 26/Jul/2022

"""

import multiprocessing as mp
import argparse
import gzip
import re
import time
import yaml
import faac
import math
from collections import OrderedDict
from math import floor
from sys import version_info
    
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
    config = faac.loadConfig(parserConfig, 'fclearner', debugmode)

    # Print configuration summary
    configSummary(config)

    # Count data entries
    stats = create_stats(config)
    stats = count_entries(config,stats) 

    # Parse
    output_data = parsing(config, startTime, stats)

    # Filter output => Only filter during processing, not here, so we identify features that at relevant during a certain interval
    output_data = filter_output(output_data, config['EndLperc'], config['Lperc'])

    # write in stats file
    write_stats(config, stats)

    # Output results
    write_output(config, output_data, stats['total_lines'])
            

    print ("Elapsed: %s \n" %(prettyTime(time.time() - startTime))    )



def parsing(config,startTime,stats):
    '''
    Main process for parsing. The program is in charge of temporal sampling.
    '''
    results = {}

    for source in config['SOURCES']:
        results[source] = []
        currentTime = time.time()
        print ("\n-----------------------------------------------------------------------\n")
        print ("Elapsed: %s \n" %(prettyTime(currentTime - startTime)))


        results[source] = process_multifile(config, source, stats)


    return results


def process_multifile(config, source, stats):
    '''
    processing files procedure in offline parsing. In this function the pool 
    of proccesses is created. Each file is fragmented in chunk sizes that can be load to memory. 
    Each process is assigned a chunk of file to be processed.
    The results of each process are gathered to be postprocessed. 
    '''
    results = {}
    count = 0
    lengths = stats['sizes'][source] #filesize
    
    for i in range(len(config['SOURCES'][source]['FILESTRAIN'])):
        input_path = config['SOURCES'][source]['FILESTRAIN'][i]
        if input_path:
            count += 1
            tag = getTag(input_path)
            cont = True
            init = 0
            remain = lengths[i]

            #Print some progress stats
            print ("%s  #%s / %s  %s" %(source, str(count), str(len(config['SOURCES'][source]['FILESTRAIN'])), tag))
         
            # Recalculate Ncores if nlogs < ncores for this datasource
            ncores_bkp = config['Cores']
            nlogs = stats['lines'][source]
            if config['Cores']>1 and 10*config['Cores'] > nlogs:     
                config['Cores'] = max(1, floor(nlogs/10))
             
            # Multiprocessing   
            pool = mp.Pool(config['Cores'])
            while cont:         # cleans memory from processes
                jobs = list()
                # Initially, data is split into chunks with size: min(filesize, max_chunk) / Ncores
                for fragStart,fragSize in frag(input_path,init,config['RECORD_SEPARATOR'][source], int(math.ceil(float(min(remain,config['Csize']))/config['Cores'])),config['Csize']):
                    jobs.append( pool.apply_async(process_file,(input_path,fragStart,fragSize,config, source)) )
                else:
                    if fragStart+fragSize < lengths[i]:
                        remain = lengths[i] - fragStart+fragSize
                        init = fragStart+fragSize 
                    else:
                        cont = False

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

def process_file(file, fragStart, fragSize, config, source):
    '''
    Function that uses each process to get data entries from unstructured data using the separator defined
    in configuration files that will be transformed into observations. This is used only in offline parsing. 
    '''

    obsDict = {}
    processed_lines = 0
    separator = config['RECORD_SEPARATOR'][source]

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
        tag, instances = process_log(line, config, source)
        
        if tag == 0:
            tag = file.split("/")[-1]

        if instances is not None:
            aggregate(obsDict, instances, tag)
            processed_lines+=1
            
    return processed_lines, obsDict


def process_log(log, config, source):
    '''
    Function take on data entry as input an transform it into a preliminary observation
    '''     
        
    ignore_log = 0      # flag to skip processing this log
    if not log or not log.strip():  
        ignore_log=1    # do not process empty logs or containing only spaces
        print('\033[31m'+ "The entry log is empty and will not be processed\n" +'\033[m')

    if not ignore_log:
        
        record = faac.Record(log,config['SOURCES'][source]['CONFIG']['VARIABLES'], config['STRUCTURED'][source], config['TSFORMAT'][source], config['All'])

        instances = {}
        for variable in range(len(config['SOURCES'][source]['CONFIG']['VARIABLES'])):
            instances[config['SOURCES'][source]['CONFIG']['VARIABLES'][variable]['name']] = {}
        instances['count'] = 1
                
        timearg = config['TIMEARG'][source] # name of variable which contains timestamp
        log_timestamp = record.variables[timearg][0].value
    
        # Check if log_timestamp will be considered according to time sampling parameters
        if 'start' in config['Time']:
            if log_timestamp < config['Time']['start']:
                ignore_log = 1
        if 'end' in config['Time']:
            if log_timestamp > config['Time']['end']:
                ignore_log = 1 
        
        print(record)
            
    if not ignore_log:
        
        for variable,features in record.variables.items():
            if variable != timearg:
                if variable in instances.keys():
                    for feature in features:
                        if str(feature) in instances[variable].keys():
                            instances[variable][str(feature)] += 1
                        else:
                            instances[variable][str(feature)] = 1
                else:
                    instances[variable] = dict() 
                    for feature in features:
                        instances[variable][str(feature)] = 1

        window = config['Time']['window']     
        try:
            tag2 = normalize_timestamps(log_timestamp, window)
            tag = tag2.strftime("%Y%m%d%H%M")

        except: 
            # Exception as err
            # print("[!] Log failed. Reason: "+ (str(err) + "\nLog entry: " + repr(log[:300])+ "\nRecord value: "+ str(record)))
            tag, instances = None, None
            if debugmode:
                print('\033[31m'+ "This entry log would be ignored due to errors" +'\033[m')

                    
    else:
        tag, instances = None, None
        
    print(tag)
    print(instances)
    return tag, instances


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
        

def aggregate(obsDict, instances_new, tag):
    '''
    Aggregate counters
    '''     

    #instances_new = filter_instances(instances_new, perc)
    
    if tag in list(obsDict.keys()):
        instances = obsDict[tag]
        
        instances['count'] += instances_new['count']
        
        for variable,features in instances_new.items():
            if variable != 'count':
                if variable in instances.keys():
                    for feature in features:
                        if feature in instances[variable].keys():
                            instances[variable][feature] += instances_new[variable][feature]
                        else:
                            instances[variable][feature] = instances_new[variable][feature]
                else:
                    instances[variable] = dict() 
                    for feature in features:
                        instances[variable][feature] = instances_new[variable][feature]
                        
        obsDict[tag] = instances
        
    else:
        obsDict[tag] = instances_new
        
    return obsDict


def iter_split(line, delimiter):
    start = 0
    line_size = len(line)
    delimiter_size = len(delimiter)
    while start<line_size:
        end = line.find(delimiter, start)
        yield line[start:end]
        if end == -1: break
        start = end + delimiter_size

 
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
    statsStream = open(statsPath, 'w')
    statsStream.write("STATS\n")
    statsStream.write("=================================================\n\n")

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
        for file in config['SOURCES'][source]['FILESTRAIN']:
            
            if config['STRUCTURED'][source]:
                (l,s) = file_len(file)
                lines[source] += l
                stats['sizes'][source].append(s)
                
            # unstructured source
            else:
                (l,s) = file_uns_len(file,config['RECORD_SEPARATOR'][source])
                lines[source] += l
                stats['sizes'][source].append(s)
    

    # Sum lines from all datasources to obtain tota lines.
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
    parser.add_argument('config', metavar='CONFIG', help='learner Configuration File.')
    parser.add_argument('-d', '-g', '--debug', action='store_true', help="Run fclearner in debug mode")
    args = parser.parse_args()
    return args


def configSummary(config):
    '''
    Print a summary of loaded parameters
    '''

    print ("-----------------------------------------------------------------------")
    print ("Data Sources:")
    for source in config['SOURCES']:
        print (" * %s %s variables " %((source).ljust(18), str(len(config['SOURCES'][source]['CONFIG']['VARIABLES'])).ljust(2)))
    print ()
    print ("Output:")
    print ("  Directory: %s" %(config['OUTDIR']))
    print ("  Stats file: %s" %(config['OUTSTATS']))
    print ("-----------------------------------------------------------------------\n")
    



def filter_output(output_data, percT, percL):
    '''Filter de data to only common features
    '''
    for source in output_data.keys():
        output_data[source] = filter_instances(output_data[source], percT, percL)


    return output_data


def filter_instances(instances, percT, percL):
    '''Filter de data to only common features
    '''
        
    for tag in instances.keys(): # Local thresholding per window
        delvar = []
        for varkey in instances[tag].keys():
            if varkey != 'count':
                delfea = []
    
                for feakey in instances[tag][varkey].keys(): 
                    if instances[tag][varkey][feakey] < percL*instances[tag]['count']:
                        delfea.append(feakey)
                    
                for feakey in delfea:
                    del instances[tag][varkey][feakey]
                    if len(instances[tag][varkey].keys()) == 0:
                        delvar.append(varkey)
                        
        for varkey in delvar:
            del instances[tag][varkey] 
                    
                    
    obsDict = {} # Aggregate instances from the list of windows  
    obsDict['count'] = 0
    for tag in instances.keys():             
        for variable,features in instances[tag].items():
            if variable != 'count':
                if variable in obsDict.keys():
                    for feature in features:
                        if feature in obsDict[variable].keys():
                            obsDict[variable][feature] += instances[tag][variable][feature]
                        else:
                            obsDict[variable][feature] = instances[tag][variable][feature]
                else:
                    obsDict[variable] = dict() 
                    for feature in features:
                        obsDict[variable][feature] = instances[tag][variable][feature]
                        
            else:
                obsDict['count'] += instances[tag]['count']
    
    
    threshold = percT*obsDict['count'] 
    delvar = []
    for varkey in obsDict.keys():
        if varkey != 'count':
            delfea = []
    
            for feakey in obsDict[varkey].keys():
                if obsDict[varkey][feakey] < threshold:
                    delfea.append(feakey)
                    
            for feakey in delfea:
                del obsDict[varkey][feakey]
                if len(obsDict[varkey].keys()) == 0:
                    delvar.append(varkey)
                    
    for varkey in delvar:
        del obsDict[varkey] 

    return obsDict
                    

def write_stats(config,stats):
    
    statsStream = open(stats['statsPath'], 'a')

    for source in config['SOURCES']:
        statsStream.write( " * %s \n" %((source).ljust(18)))
        statsStream.write( "\t\t %s variables \n" %(len(config['SOURCES'][source]['CONFIG']['VARIABLES'])))
        statsStream.write( "\t\t %d logs - %d processed logs \n" %(stats['lines'][source], stats['processed_lines'][source]))
        statsStream.write( "\t\t %d total bytes (%.2f MB) \n\n" %(sum(stats['sizes'][source]),
                                                           (sum(stats['sizes'][source]))*1e-6))

    statsStream.write("\n=================================================\n\n")

    statsStream.close()

def write_output(config, output_data, total):
    '''Write configuration file
    '''
    
    print(output_data)

    contentf = dict()
    contentf['FEATURES'] = list()

    yaml.add_representer(UnsortableOrderedDict, yaml.representer.SafeRepresenter.represent_dict)

    for source in output_data.keys():
        print ("\nWriting configuration file " + config['SOURCES'][source]['CONFILE'] + "\n") 
        for varkey in output_data[source].keys():
            if varkey != 'count':

                l = OrderedDict(sorted(output_data[source][varkey].items(), key=lambda t: t[1], reverse=True))
                for feakey in l.keys():

                    interm = UnsortableOrderedDict()
                    interm['name'] = source + '_' + varkey + '_' + feakey.replace(" ", "").replace("\'", "\'\'").replace("\"", "\"\"")
                    interm['variable'] = varkey
                    interm['matchtype'] = 'single'
                    interm['value'] =  feakey.replace("\'", "\'\'").replace("\"", "\"\"") 
                    interm['weight'] = output_data[source][varkey][feakey]/float(total)
                    contentf['FEATURES'].append(interm)

        for i in range(len(config['SOURCES'][source]['CONFIG']['VARIABLES'])):
            vType = config['SOURCES'][source]['CONFIG']['VARIABLES'][i]['matchtype']
            vName = config['SOURCES'][source]['CONFIG']['VARIABLES'][i]['name']
            timearg = config['TIMEARG'][source] # name of variable which contains timestamp

            if vName != timearg:
                if vType == 'string':
                    interm = UnsortableOrderedDict()
                    interm['name'] = source + '_' + vName + '_default'
                    interm['variable'] = vName
                    interm['matchtype'] = 'default'
                    interm['value'] = ''
                    interm['weight'] = 1
                    contentf['FEATURES'].append(interm)
                elif vType == 'number':
                    interm = UnsortableOrderedDict()
                    interm['name'] = source + '_' + vName + '_default'
                    interm['variable'] = vName
                    interm['matchtype'] = 'default'
                    interm['value'] = ''
                    interm['weight'] = 1
                    contentf['FEATURES'].append(interm)
                elif vType == 'ip':
                    interm = UnsortableOrderedDict()
                    interm['name'] = source + '_' + vName + '_private'
                    interm['variable'] = vName
                    interm['matchtype'] = 'single'
                    interm['value'] = 'private'
                    interm['weight'] = 1
                    contentf['FEATURES'].append(interm)

                    interm = UnsortableOrderedDict()
                    interm['name'] = source + '_' + vName + '_public'
                    interm['variable'] = vName
                    interm['matchtype'] = 'single'
                    interm['value'] = 'public'
                    interm['weight'] = 1
                    contentf['FEATURES'].append(interm)

        # write resuls in yaml
        try:
            f = open(config['SOURCES'][source]['CONFILE'], 'a')
            f.write('\n\n')
            yaml.dump(contentf, f, default_flow_style=False)
        except:
                print ("Problem writing YAML file")
                quit()
        finally:
            f.close()

    

class UnsortableList(list):
    def sort(self, *args, **kwargs):
        pass

class UnsortableOrderedDict(OrderedDict):
    def items(self, *args, **kwargs):
        return UnsortableList(OrderedDict.items(self, *args, **kwargs))


if __name__ == "__main__":
    
    if version_info[0] != 3:
        print('\033[31m'+ "** PYTHON VERSION ERROR **" +'\033[m')
        print("Please, use python3 to run this program")
        exit(1)
        
    main()
