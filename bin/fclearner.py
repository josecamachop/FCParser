#!/usr/bin/env python

"""
learner -- Program for automatically learning features from the set of variables
of raw network data using the FaaC parser library.


Authors:    Jose Camacho (josecamacho@ugr.es)
         
Last Modification: 26/Jul/2022

"""

import multiprocessing as mp
from collections import OrderedDict
import argparse
import gzip
import re
import time
import yaml
import faac
import math
from math import floor
    
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
    output_data = filter_output(output_data, config['EndLperc'])

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
    instances = {}
    for variable in range(len(config['SOURCES'][source]['CONFIG']['VARIABLES'])):
        instances[config['SOURCES'][source]['CONFIG']['VARIABLES'][variable]['name']] = {}

    count = 0
    instances['count'] = 0
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
                    instances = combine(instances,job.get(),config['Lperc'])


            pool.close()
            config['Cores'] = ncores_bkp
    
    return instances

def process_file(file, fragStart, fragSize, config, source):
    '''
    Function that uses each process to get data entries from unstructured data using the separator defined
    in configuration files that will be transformed into observations. This is used only in offline parsing. 
    '''

    instances = {}
    separator = config['RECORD_SEPARATOR'][source]
    
    try:    
        if file.endswith('.gz'):                    
            f = gzip.open(file, 'r')
        else:
            f = open(file, 'r')

        f.seek(fragStart)
        lines = f.read(fragSize)
    
    finally:
        f.close()

    instances['count'] = 0
    log = ''
    for line in lines:
        log += line 

        if separator in log:
            instances = process_log(log,config, source, instances)
            log = log.split(separator)[1]
    if log:    
        instances = process_log(log,config, source, instances)


    return instances

def frag(fname, init, separator, size, max_chunk):
    '''
    Function to fragment files in chunks to be parallel processed for structured files by lines
    '''

    #print "File pos: %d, size: %d, max_chunk: %d" %(init,size, max_chunk)

    try:
        if fname.endswith('.gz'):                    
            f = gzip.open(fname, 'r')
        else:
            f = open(fname, 'r')


        f.seek(init)
        end = f.tell()
        init = end
        cont = True
        while end-init < max_chunk:
            start = end
            asdf = f.read(size)
            i = asdf.rfind(separator)
            if i == -1:
                break

            f.seek(start+i+1)
            end = f.tell()

            yield start, end-start



    finally:
        f.close()

def combine(instances, instances_new, perc):
    '''
    Combine counters
    '''     

    instances_new = filter_instances(instances_new, perc)

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


    return instances







def process_log(log, config, source, instances):
    '''
    Function take on data entry as input an transform it into a preliminary observation
    '''     
    timearg = config['TIMEARG'][source] # name of variable which contains timestamp
    record = faac.Record(log,config['SOURCES'][source]['CONFIG']['VARIABLES'], config['STRUCTURED'][source], config['SOURCES'][source]['CONFIG']['timestamp_format'], config['All'])

    instances['count'] += 1

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

                    

    return instances
    

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
    stats['sizes'] = {}
    for source in config['SOURCES']:
        lines[source] = 0
        stats['sizes'][source] = list()
        for file in config['SOURCES'][source]['FILESTRAIN']:
            if config['STRUCTURED'][source]:
                (l,s) = file_len(file)
                lines[source] += l
                stats['sizes'][source].append(s)

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

    statsStream = open(stats['statsPath'], 'a')

    for source in config['SOURCES']:
        statsStream.write( " * %s \n" %((source).ljust(18)))
        statsStream.write( "\t\t %s variables \n" %(len(config['SOURCES'][source]['CONFIG']['VARIABLES'])))
        statsStream.write( "\t\t %d logs \n" %(stats['lines'][source]))
        statsStream.write( "\t\t %d bytes \n" %(sum(stats['sizes'][source])))

    statsStream.write("\n\n=================================================\n\n")

    statsStream.close()

    return stats

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
    print ("  Stats file: %s" %(config['OUTSTATS']))
    print ("-----------------------------------------------------------------------\n")
    


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

    return count_log,size


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


def filter_output(output_data,perc):
    '''Filter de data to only common fatures
    '''
    for source in output_data.keys():
        output_data[source] = filter_instances(output_data[source],perc)


    return output_data


def filter_instances(instances, perc):
    '''Filter de data to only common fatures
    '''
    threshold = perc*instances['count']
    for varkey in instances.keys():
        if varkey != 'count':
            for feakey in instances[varkey].keys():
                if instances[varkey][feakey] < threshold:
                    del instances[varkey][feakey]
            if len(instances[varkey].keys()) == 0:
                del instances[varkey]


    return instances
                    


def write_output(config, output_data, total):
    '''Write configuration file
    '''

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
                print ("Problem writing " + yamlfile)
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
    
    main()
