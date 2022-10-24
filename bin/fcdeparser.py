"""
deparser -- This program take as input the features and the timestamps
obtained from data analysis in order to extract the small amount of 
data related to anomalies in comparison to masive amounts of extracted data

Authors:  Manuel Jurado Vázquez (manjurvaz@ugr.es)
          Jose Manuel Garcia Gimenez (jgarciag@ugr.es)
          Jose Camacho (josecamacho@ugr.es)
         
Last Modification: 24/Oct/2022

"""

import multiprocessing as mp
import argparse
import os
import gzip
import re
import time
import faac
import math
from datetime import datetime 
import linecache
from sys import version_info


def main(call='external', configfile=''):
    
    global startTime; startTime = time.time()

    # If called from terminal. If not, the parser must be called in this way: fcdeparser.main(call='internal',configfile='<route_to_config_file>')
    if call == 'external':
        args = getArguments()
        configfile = args.config
        deparsfile = args.input
        global debugmode; debugmode = args.debug    # debugmode defined as global as it will be used in many functions

    # Get configuration
    parserConfig = faac.getConfiguration(configfile)
    config = faac.loadConfig(parserConfig, 'fcdeparser', debugmode)
    deparsInput = getDeparsInput(deparsfile, config)
    
    # Show init message with features and timestamps from deparsInput
    initMessage(deparsInput, debugmode)        
        
    # Counters for total logs and found logs during deparsing process
    count_structured = 0    # structured logs found
    count_unstructured = 0  # unstructured logs found 
    count_tots = 0          # total structured logs
    count_totu = 0          # total unstructured logs
    
    # Iterate through features and timestamps
    if deparsInput['features']:
        for source in config['SOURCES']:
            if not debugmode:
                print ("---------------------------------------------------------------------------")
                print("\nLoading '%s' data source..." %(source))
            
            sourcepath = config['SOURCES'][source]['FILESDEP']
            formated_timestamps = format_timestamps(deparsInput['timestamps'], config['TSFORMAT'][source])
            
            # Structured sources
            if config['STRUCTURED'][source]:
                (cs, ct) = stru_deparsing(config, sourcepath, deparsInput, source, formated_timestamps)
                count_structured += cs
                count_tots += ct

            # Unstructured sources
            else:
                (cu, ct) = unstr_deparsing(config, sourcepath, deparsInput,source, formated_timestamps)
                count_unstructured += cu
                count_totu += ct

            print ("Elapsed: %s" %(prettyTime(time.time() - startTime)))

    if not debugmode:
        stats(count_structured, count_tots, count_unstructured, count_totu, config['OUTDIR'], config['OUTSTATS'], startTime)

    


def print_loadSummary(config,deparsInput,startTime):
    '''
    Print a summary of loaded parameters
    '''
    print ("------------------------------------------------------------------------")
    print ("Data Sources:")
    for source in config['sources_files']:
                print ("    - " + str(config['tags'][source]) + " --> Files: " + str(config['sources_files'][source]['files']))

    print ("FEATURES:")
    print (" TOTAL " + (str(len(deparsInput['features']))) + " features:  \n" + str(deparsInput['features']) + "\n")
    print ("------------------------------------------------------------------------\n")

    print ("TIMESTAMPS")
    print (" TOTAL " + (str(len(deparsInput['timestamps']))) + " timestamps:  \n" + str(deparsInput['timestamps']) + "\n")
    print ("------------------------------------------------------------------------\n")
    
    print ("Output:")
    print ("  Directory: %s" %(config['OUTDIR']))
    print ("  Stats file: %s" %(config['OUTSTATS']))
    print ("\n------------------------------------------------------------------------\n")
    print ("Elapsed: %s" %(prettyTime(time.time() - startTime)))
    print ("\n------------------------------------------------------------------------\n")


def stru_deparsing(config, sourcepath, deparsInput, source, formated_timestamps):
    '''
    Deparsing process for structured data sources like csv.
    '''
    threshold = config['threshold']
    OUTDIR = config['OUTDIR']
    depars_features = deparsInput['features']  # features in deparsing_input file

    # Store features and variables from config. file in dictionaries FEATURES, VARIABLES
    FEATURES = {}
    VARIABLES = {}
    for feature in config['SOURCES'][source]['CONFIG']['FEATURES']:
        try:
            FEATURES[feature['name']] = feature
        except:
            print ("Configuration file error: missing features")
            exit(1)

    for variable in config['SOURCES'][source]['CONFIG']['VARIABLES']:
        try:
            VARIABLES[variable['name']] = variable
        except:
            print ("Configuration file error: missing variables")
            exit(1)
            
    selection = []  # indices of features in config file matching depars_features
    for i in range(len(config['FEATURES'][source])):
        if config['FEATURES'][source][i]['name'] in depars_features:
            selection.append(i)

    FEATURES_sel = []   # all feature fields for features in depars_features
    for i in selection:
        FEATURES_sel.append(config['FEATURES'][source][i])
            
    timestamp_pos = VARIABLES[config['TIMEARG'][source]]['where']   # position (column) of timestamp field


    count_structured = 0    # structured logs found during deparsing process
    count_tot = 0           # total logs
    feat_appear = {}
    feat_appear_names = {}    
    
    for file in sourcepath:
        feat_appear[file] = []
        feat_appear_names[file] = []
        
        if file.endswith('.gz'):
            input_file = gzip.open(file,'r')
        else:
            input_file = open(file,'r')

        if debugmode:
            faac.debugProgram('fcdeparser.load_message', [file])

        # Multiprocessing
        pool = mp.Pool(config['Cores'])
        cont = True
        init = 0
        length = os.path.getsize(file) 
        remain = length
        while cont:                          # cleans memory from processes
            nline=0
            jobs = list()
            # Initially, data is split into chunks with size: min(filesize, max_chunk) / Ncores
            for fragStart,fragSize in frag(input_file,init,config['RECORD_SEPARATOR'][source], int(math.ceil(float(min(remain,config['Csize']))/config['Cores'])), config['Csize']):
                if not debugmode:
                    jobs.append( pool.apply_async(process_file,[file,fragStart,fragSize,config,source,timestamp_pos,formated_timestamps,FEATURES_sel]) )
                else:
                    feat_appear_f, feat_appear_names_f, nline_f = process_file(file,fragStart,fragSize,config,source,timestamp_pos,formated_timestamps,FEATURES_sel)
                    feat_appear[file].append(feat_appear_f)
                    feat_appear_names[file].append(feat_appear_names_f)
                    nline+=nline_f
                
            else:
                if fragStart+fragSize < length:
                    remain = length - fragStart+fragSize
                    init = fragStart+fragSize 
                else:
                    if not debugmode:
                        cont = False
                    else:
                        print('\033[33m'+ "* End of file %s *" %(file) +'\033[m')
                        print("Loading file again...")
                        init=0
                        remain = length
                        global user_input; user_input = None

                            
            for job in jobs:
                job_data = job.get()
                feat_appear_f = job_data[0]
                feat_appear_names_f = job_data[1]
                nline_f = job_data[2]
                feat_appear[file].append(feat_appear_f)
                feat_appear_names[file].append(feat_appear_names_f)
                nline+=nline_f
                    
                
        input_file.close()
        count_tot+=nline    # add nlines of this source to total lines counter
        
        # Print number of matched logs for each features number (feature selection criteria)
        matched_lines = faac.debugProgram('fcdeparser.stru_deparsing.feat_appear', [feat_appear[file], depars_features, nline])
    
    
    # Obtain number of features needed to extract the log with the given threshold
    features_threshold = len(depars_features)
    indices = {}
    for file in sourcepath: indices[file]={}   # new dict for every data file
    count = 0
    
    while features_threshold>0:     # if no threshold, extract all logs with >0 matched features
        if not threshold or (threshold and count < int(threshold)): 
            nfeatures = features_threshold
            for file in feat_appear:
                count += feat_appear[file].count(int(nfeatures))
                indices[file][nfeatures] = [i for i, val in enumerate(feat_appear[file]) if val==nfeatures]
            features_threshold -= 1
        else:
            break
    
    
    if debugmode:
        opmode = faac.debugProgram('fcdeparser.stru_deparsing.user_input', [config['threshold'], features_threshold, matched_lines])
    else:
        if threshold:
            print("Considering the feature counters and a threshold of %d log entries, we will extract logs with >=%d matched features" %(config['threshold'],features_threshold+1))
        else:
            print("As no threshold is defined, we will extract all logs with >=1 matched features")
        print("Note that the output will be generated in different files according to their number of features")

        
    # Re-read the file extracting the raw data
    for file in sourcepath:
        
        if file.endswith('.gz'):
            input_file = gzip.open(file,'r')
        else:
            input_file = open(file,'r')
        
        
        if not debugmode:
            for nfeatures in indices[file]:
                if indices[file][nfeatures]:
                    output_file = open(OUTDIR + "output_%s_%sfeat" %(source,nfeatures),'a')
                    for line_index in indices[file][nfeatures]:
                        line = linecache.getline(file, line_index+1) # index starting by 1 with linecache function
                        output_file.write(line)
                        count_structured += 1
                    output_file.close()
                
        else:
            for position, line in enumerate(input_file):
                nfeatures = feat_appear[file][position]
                features_names = feat_appear_names[file][position]
                if (nfeatures>features_threshold and position in indices[file][nfeatures]) and opmode in {1,2}: 
                    faac.debugProgram('fcdeparser.stru_deparsing.deparsed_log', [position+1, line, nfeatures, features_names, opmode])
                elif opmode in {1}:
                    faac.debugProgram('fcdeparser.stru_deparsing.unmatched_criteria', [position+1, line, nfeatures, features_names])
                
                
        input_file.close()

    return (count_structured, count_tot)

def process_file(file, fragStart, fragSize, config, source, timestamp_pos, formated_timestamps, FEATURES_sel):
    
    feat_appear = []
    feat_appear_names = []

    if file.endswith('.gz'):
        filep = gzip.open(file,'r')
    else:
        filep = open(file,'r')
            
    # Multiprocessing
    line = filep.readline()
    # First read to generate a list with the number of depars_features present in each line
    nline=0   
    while line:
        nline+=1  
        try:
            t = getStructuredTime(line, timestamp_pos, config['TSFORMAT'][source])  # timestamp in that line

            # extract amount of features that appear in the line if its timestamp is included in formated_timestamps
            if t.strip() in formated_timestamps or not formated_timestamps:
                record = faac.Record(line,config['SOURCES'][source]['CONFIG']['VARIABLES'], config['STRUCTURED'][source], config['TSFORMAT'][source], config['All'])
                obs = faac.Observation.fromRecord(record, FEATURES_sel)         # to make default features counter work properly, use config['FEATURES'][source] instead of FEATURES_sel (but execution will be significantly slower)
                feature_count, matched_features = search_features_str(obs, VARIABLES)
                feat_appear.append(feature_count)
                feat_appear_names.append(matched_features)
                    
            else:
                # it is necessary to fill with zeros so that indices match the lines later
                feat_appear.append(0) 
                feat_appear_names.append([])
                
        except Exception as error:
            print ('\033[33m'+ "Error finding features in line %d: %s" %(nline,error) +'\033[m')
            feat_appear.append(0)
            feat_appear_names.append([])
                    
        line = filep.readline()
        
    filep.close()
            
    return (feat_appear, feat_appear_names, nline)

def unstr_deparsing(config, sourcepath, deparsInput, source, formated_timestamps):
    '''
    Deparsing process for unstructured text based data sources like a log file.
    '''
    threshold = config['threshold']
    OUTDIR = config['OUTDIR']
    depars_features = deparsInput['features']
    timearg = config['TIMEARG'][source] # name of the variable which contains timestamp 

    selection = []  # indices of features in config file matching depars_features
    for i in range(len(config['FEATURES'][source])):
        if config['FEATURES'][source][i]['name'] in depars_features:
            selection.append(i)

    FEATURES_sel = []   # all feature fields for features in depars_features
    for i in selection:
        FEATURES_sel.append(config['FEATURES'][source][i])

    VARIABLES = {}  # all variables from config file

    for variable in config['SOURCES'][source]['CONFIG']['VARIABLES']:
        try:
            VARIABLES[variable['name']] = variable
        except:
            print ("Configuration file error: missing variables")
            exit(1)
    
    count_unstructured = 0
    count_tot = 0

    # while count_source < lines[source]*0.01 and (not features_needed <= 0) : 
    feat_appear = {}
    indices = {}
    for file in sourcepath:
        feat_appear[file] = []   
        indices[file] = {}
        for nfeatures in range(len(depars_features),0,-1):
            indices[file][nfeatures] = []   # dict of dicts for each number of features

        if file.endswith('.gz'):
            input_file = gzip.open(file,'r')
        else:
            input_file = open(file,'r')
            
        if debugmode:
            faac.debugProgram('fcdeparser.load_message', [file])


        # First read to generate list of number of appearances
        line = input_file.readline()
        nline=0
        log_indices = []

        if line:
            log = "" 
            log_indices.append(nline+1)
            while line:
                nline+=1
                log += line 
    
                if len(log.split(config['RECORD_SEPARATOR'][source])) > 1:
                    count_tot+=1
                    log_indices.append(nline)
                    logExtract = log.split(config['RECORD_SEPARATOR'][source])[0]
                    
                    # For each log, extract timestamp with regular expresions and check if in formated_timestamps
                    try:
                        t = getUnstructuredTime(logExtract, VARIABLES[timearg]['where'], config['TSFORMAT'][source])                    
                        if str(t).strip() in formated_timestamps or not formated_timestamps:    
                            # Check if features appear in the log in order to write in the file later
                            record = faac.Record(logExtract,config['SOURCES'][source]['CONFIG']['VARIABLES'], config['STRUCTURED'][source], config['TSFORMAT'][source], config['All'])
                            obs = faac.Observation.fromRecord(record, FEATURES_sel)
                            feature_count = sum( [obs.data[i].value for i in range(len(obs.data))] )
                            feat_appear[file].append(feature_count)
                            indices[file][feature_count].append(log_indices)
                    except:
                        pass
                        
                    log = ""
                    log_indices = [nline+1] # reset log_indices adding first line of next log
                    for n in logExtract.split(config['RECORD_SEPARATOR'][source])[1::]:
                        log += n    # if next log in the same line, add remaining part
                        log_indices = [nline]   # in this case, next log first index is actual line
                
                line = input_file.readline()

            # Deal with the last log, not processed during while loop.
            log += line
            log_indices.append(nline)
            try:                                
                t = getUnstructuredTime(log, VARIABLES[timearg]['where'], config['TSFORMAT'][source])
                if str(t) in formated_timestamps or not formated_timestamps:
                    record = faac.Record(logExtract,config['SOURCES'][source]['CONFIG']['VARIABLES'], config['STRUCTURED'][source], config['TSFORMAT'][source], config['All'])
                    obs = faac.Observation.fromRecord(record, FEATURES_sel)
                    feature_count = sum( [obs.data[i].value for i in range(len(obs.data))] )
                    feat_appear[file].append(feature_count)
                    indices[file][feature_count].append(log_indices)
                    
            except:
                pass

        input_file.close()
        
        # Print number of matched logs for each features number (feature selection criteria)
        matched_logs = faac.debugProgram('fcdeparser.unstr_deparsing.feat_appear', [feat_appear[file], depars_features])

        
    # Obtain number of features needed to extract the log with the given threshold
    features_threshold = len(depars_features)
    count = 0
    while features_threshold>0:     # if no threshold, extract all logs with >0 matched features
        if not threshold or (threshold and count < int(threshold)): 
            nfeatures = features_threshold
            for file in feat_appear:
                count += feat_appear[file].count(int(nfeatures))
            features_threshold -= 1
        else:
            break
    
        
    if debugmode:
        opmode = faac.debugProgram('fcdeparser.unstr_deparsing.user_input', [config['threshold'], features_threshold, matched_logs])
    else:
        if threshold:
            print("Considering the feature counters and a threshold of %d log entries, we will extract logs with >=%d matched features" %(config['threshold'],features_threshold+1))
        else:
            print("As no threshold is defined, we will extract all logs with >=1 matched features")
        print("Note that the output will be generated in different files according to their number of features")
        
        
    #Re-read desired lines
    for file in sourcepath:
    
        if file.endswith('.gz'):
            input_file = gzip.open(file,'r')
        else:
            input_file = open(file,'r')  
            

        if not debugmode:
            for nfeatures in range(len(depars_features),features_threshold,-1):
                if indices[file][nfeatures]:
                    output_file = open(OUTDIR + "output_%s_%sfeat" %(source,nfeatures),'a')
                    for line_indices in indices[file][nfeatures]:
                        log=""
                        for index in range(line_indices[0], 1+line_indices[1]):
                            log+=linecache.getline(file, index)
                        
                        logExtract = log.split(config['RECORD_SEPARATOR'][source])[0]
                        if log.split(config['RECORD_SEPARATOR'][source])[1]: 
                            logExtract = log.split(config['RECORD_SEPARATOR'][source])[1] # if characters after the separator, take them instead
                        output_file.write(logExtract + config['RECORD_SEPARATOR'][source])
                        count_unstructured += 1
                    output_file.close()
                
        else:
            index = 0
            index_deparsed = 0
            line = input_file.readline()
                
            if line:
                log = ""     
                while line:
                    log += line 
                    if len(log.split(config['RECORD_SEPARATOR'][source])) > 1:
                        logExtract = log.split(config['RECORD_SEPARATOR'][source])[0]
                        try:
                            t = getUnstructuredTime(logExtract, VARIABLES[timearg]['where'], config['TSFORMAT'][source])     
                            if str(t).strip() in formated_timestamps or not formated_timestamps:
                                if feat_appear[file][index_deparsed] > features_threshold and opmode in {1,2}:    
                                    faac.debugProgram('fcdeparser.unstr_deparsing.deparsed_log', [index+1, logExtract, feat_appear[file][index_deparsed], opmode])
                                elif opmode in {1}:
                                    faac.debugProgram('fcdeparser.unstr_deparsing.unmatched_criteria1', [index+1, logExtract, feat_appear[file][index_deparsed]])
                                index_deparsed+=1
                            elif opmode in {1}:
                                faac.debugProgram('fcdeparser.unstr_deparsing.unmatched_criteria2', [index+1, logExtract])
                            index += 1
                        except SystemExit:
                            exit(1)
                        except:
                            pass

                        log = ""
                        for n in logExtract.split(config['RECORD_SEPARATOR'][source])[1::]:
                            log += n
                    line = input_file.readline()

        
        input_file.close()
    
    return (count_unstructured, count_tot)


def format_timestamps(timestamps, source_format):
    '''
    Format a list of timestamps (with t_format) to the data source timestamp format (source_format)
    '''
    
    timestamps_formated= []
    t_format = "%Y-%m-%d %H:%M:%S"   # timestamp format for timestamps in deparsing_input file

    for t in timestamps:
        timestamps_formated.append(str(datetime.strptime(t, t_format).strftime(source_format)))

    return timestamps_formated


def frag(filep, init, separator, size, max_chunk):
    '''
    Function to fragment files in chunks to be parallel processed for structured files by lines
    '''
    #print ("File pos: %d, size: %d, max_chunk: %d", init, size, max_chunk)
    
    filep.seek(init)
    end = filep.tell()
    init = end
    separator_size = len(separator)
    while end-init < max_chunk:
        start = end
        tmp = filep.read(size)
        i = tmp.rfind(separator)
        if i == -1:
            yield start, len(tmp)
            break
        filep.seek(start+i+separator_size)
        end = filep.tell()
        #print("Frag: "+str([start, i, end]))

        yield start, end-start

        
def stats( count_structured, count_tots, count_unstructured, count_totu, OUTDIR, OUTSTATS, startTime):
    '''
    Print and write stats from the deparsing process
    '''

    print ("---------------------------------------------------------------------------")   
    print ("\nSearch finished:")
    print ("Elapsed: %s" %(prettyTime(time.time() - startTime)))
    # print "\n Nfdump queries: " + str(count_nf)
    print (" Structured logs found:  " + str(count_structured) + ' out of ' + str(count_tots)) 
    print (" Unstructured logs found: " + str(count_unstructured) + ' out of ' + str(count_totu))
    print ("\n---------------------------------------------------------------------------\n")

    # Write stats in stats.log file.
    try:
        stats_file = open(OUTDIR + OUTSTATS,'w')
        stats_file.write("STATS:\n")
        stats_file.write("---------------------------------------------------------------------------\n")
        # stats_file.write("Nfdump queries: " + str(count_nf) + "\n")
        stats_file.write(" Structured logs found: " + str(count_structured) + ' out of ' + str(count_tots) + "\n")
        stats_file.write(" Unstructured logs found: " + str(count_unstructured) + ' out of ' + str(count_totu))

    except IOError as e:
        print ("Stats file error: " + str(e))
    

def prettyTime(elapsed):
    '''
    Function to change format of the time, for a nice representation.
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


def getUnstructuredTime (log, regexp, timestamp_format):
    '''
    # Fuction to extract timestamp from an unstructured source
    '''
    p = re.search(regexp, log)
    try:
        rawTime = p.group(0)
        time = datetime.strptime(rawTime, timestamp_format)
        time = time.replace(second = 00)
        if time.year == 1900:
            time = time.replace(year = datetime.now().year)      
        
        return time.strftime(timestamp_format)

    except:
        return None


def getStructuredTime(line, pos, timestamp_format):
    '''
    # Fuction to extract timestamp from an structured source
    '''

    valueList = line.split(',')
    rawTime = valueList[pos]
    time = datetime.strptime(rawTime, timestamp_format)
    time = time.replace(second = 00)                # ignore seconds
    time = time.replace(microsecond = 00)           # ignore microseconds
    
    return time.strftime(timestamp_format)


def getDeparsInput(deparsfile,config):
    '''
    Extract the information from the detection step (timestamps and features) for the anomaly that 
    is desired to be deparsed
    '''
    deparsInput = {}

    try:
        input_file = open(deparsfile, 'r')
    except IOError:
        print ("No such input file '%s'" %(deparsfile))
        exit(1)

    #Extract features and timestams from the input file.
    line = input_file.readline()

    features = []
    timestamps = []
    featuresBol = False
    timeBol = False

    while line:
        if "features:" in line:
            featuresBol = True

        if "timestamps:" in line:
            timeBol = True
            featuresBol = False

        if featuresBol:
            try: 
                features.append(line.split("=")[1].strip())
            except:
                pass

        if timeBol:
            try: 
                timestamps.append(line.split("=")[1].strip())
            except:
                pass
        
        line = input_file.readline()

    if not (config['Time']['window'] == 1  or config['Time']['window'] == None):
        temp = []
        for timestamp in timestamps:
            #print (timestamp)
            try:
                for i in range(config['Time']['window'] ):
                    t = datetime.strptime(timestamp,"%Y-%m-%d %H:%M:%S")
                    new_minute = (t.minute + i) % 60
                    new_hour = int((t.hour + i/60) % 24)
                    new_day = int((t.day + i/(24*60)))
                    t = t.replace(day = new_day, hour = new_hour, minute = new_minute, second = 0)    
                    temp.append(str(t))
            except:
                print(t)

        timestamps = temp

    deparsInput['features'] = features
    deparsInput['timestamps'] = timestamps
    
    return deparsInput    


def getArguments():
    '''
    Function to get input arguments using argparse.
    For more info about the arguments, run fcdeparser.py -h
    '''

    parser = argparse.ArgumentParser(formatter_class = argparse.RawDescriptionHelpFormatter,
    description='''Multivariate Analysis Deparsing Tool.''')
    parser.add_argument('config', metavar = 'CONFIG', help = 'Deparser Configuration File.')
    parser.add_argument('input', metavar = 'DEPARSING_INPUT', help = 'Input file (vars and timestamps from multivariate analysis)')
    parser.add_argument('-d', '-g', '--debug', action='store_true', help="Run fcdeparser in debug mode")
    args = parser.parse_args()
    return args


def initMessage(deparsInput, debugmode):
    '''
    Function to show init message with deparsing input info
    '''
    
    if debugmode:
        print('\033[33m'+ "Initializing debug mode...")
        print("---------------------------------------------------------------------------\n")
        print("\t\t\tFCDEPARSER DEBUGGING MODE")
        print("\n---------------------------------------------------------------------------")
    else:
        print('\033[33m'+"Loading FCdeparser... Run program in debug mode with -d option in order to check the selection criteria in more detail"+'\033[m')
        print ("\n-------------------------------- FCDEPARSER -------------------------------")
         
    print("* Loaded Deparsing input file."+'\033[m')
    print("- Features to search: %s" %(deparsInput['features']))
    if deparsInput['timestamps']:
        if debugmode:
            print("- In logs with timestamps: %s" %(deparsInput['timestamps']))
    else:
        print("- In any log (not specified timestamps)")
    
    return  


def search_features_str(obs, VARIABLES):
    """
    Function that take record and observation from line and return the count of
    matched features and the associated feature name and variable position (which
    will be used for debugger)
    """
    
    matched_features = []
    feature_count = sum([obs.data[i].value for i in range(len(obs.data))])
    
    if debugmode:
        obs_value_list = [obs.data[i].value for i in range(len(obs.data))]
        feature_index = [i for i, j in enumerate(obs_value_list) if j != 0] # matched features index (non zero counters)
        for index in feature_index:
            fName = obs.data[index].fName
            fVariable = obs.data[index].fVariable
            pos = VARIABLES[fVariable]['where']
            matched_features.append({fName:pos})
    
    return feature_count, matched_features


"""
# OLD implementation for search_features_str (3x faster but does not make use of faac and it might not be consistent with fcparser)
def search_features_str(line, depars_features, FEATURES, VARIABLES):
    '''
    Function that take as an input one data record and obtain the number of features that appear in the log 
    from the input features for structured sources    
    '''

    feature_count = 0
    matched_features = []     # List of matched feature names
    
    for feature in depars_features:
        
        try:
            old_feature_count = feature_count
            
            fName = FEATURES[feature]['name']
            fVariable = FEATURES[feature]['variable']
            fType = FEATURES[feature]['matchtype']
            fValue = FEATURES[feature]['value']
            variable = VARIABLES[fVariable]

            pos = variable['where']

            line_split = line.split(',')

            if fType == 'regexp':        
                try:
                    re.search(fValue, line_split[pos])
                    feature_count += 1
                except:
                    pass

            elif fType == 'single':        
                if line_split[pos].strip() == str(fValue):
                    feature_count += 1

            elif fType == 'range':        

                start = fValue[0]
                end   = fValue[1]
                
                if (end is None or str(end).lower() == 'inf') and int(line_split[pos]) >= start:
                    feature_count += 1
                elif (int(line_split[pos]) <= end) and (int(line_split[pos]) >= start):
                    feature_count += 1 

            elif fType == 'multiple':
                if int(line_split[pos]) in fValue:
                    feature_count += 1
                
                
            if (feature_count>old_feature_count):
                matched_features.append({fName:pos})
                
        except:
             pass

    return (feature_count, matched_features)
"""

    
if __name__ == "__main__":
    
    if version_info[0] != 3:
        print('\033[31m'+ "** PYTHON VERSION ERROR **" +'\033[m')
        print("Please, use python3 to run this program")
        exit(1)
        
    main()
