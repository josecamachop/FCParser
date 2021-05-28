"""
deparser -- This program take as input the features and the timestamps
obtained from data analysis in order to extract the small amount of 
data related to anomalies in comparison to masive amounts of extracted data

Authors:  Manuel Jurado Vázquez (manjurvaz@ugr.es)
          Jose Manuel Garcia Gimenez (jgarciag@ugr.es)
         
Last Modification: 27/May/2021

"""

import argparse
import time
import gzip
import yaml
import faac
from datetime import datetime 
import re
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

            #print ("\n---------------------------------------------------------------------------\n")
            print ("Elapsed: %s" %(prettyTime(time.time() - startTime)))
            #print ("\n---------------------------------------------------------------------------\n")

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
    #sources_config = config['SOURCES']  - WHAT IS THIS FOR
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

        line = input_file.readline()
        # First read to generate a list with the number of depars_features present in each line
        nline=0   
        while line:
            nline+=1  
            try:
                t = getStructuredTime(line, timestamp_pos, config['TSFORMAT'][source])  # timestamp in that line

                # extract amount of features that appear in the line if its timestamp is included in formated_timestamps
                if t.strip() in formated_timestamps or not formated_timestamps:
                    feature_count, matched_features = search_features_str(line, depars_features, FEATURES, VARIABLES)
                    feat_appear[file].append(feature_count)
                    feat_appear_names[file].append(matched_features)
                else:
                    feat_appear[file].append(0)
                    feat_appear_names[file].append([])
                    
            except Exception as error:
                if debugmode:
                    print ('\033[33m'+ "Error finding features in line %d: %s" %(nline,error) +'\033[m')
                feat_appear[file].append(0)
                feat_appear_names[file].append([])
                    
            line = input_file.readline()
        input_file.close()
        count_tot+=nline    # add nlines of this source to total lines counter
        
        if debugmode:
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
                output_file = open(OUTDIR + "output_%s_%sfeat" %(source,nfeatures),'w')
                for line_index in indices[file][nfeatures]:
                    line = linecache.getline(file, line_index)
                    output_file.write(line + "\n")
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


def unstr_deparsing(config, sourcepath, deparsInput, source, formated_timestamps):
    '''
    Deparsing process for unstructured text based data sources like a log file.
    '''
    threshold = config['threshold']
    OUTDIR = config['OUTDIR']
    depars_features = deparsInput['features']
    timearg = config['TIMEARG'][source] # name of the variable which contains timestamp 

    selection = []
    for i in range(len(config['FEATURES'][source])):
        if config['FEATURES'][source][i]['name'] in depars_features:
            selection.append(i)

    FEATURES_sel = []
    for i in selection:
        FEATURES_sel.append(config['FEATURES'][source][i])

    VARIABLES = {}

    for variable in config['SOURCES'][source]['CONFIG']['VARIABLES']:
        try:
            VARIABLES[variable['name']] = variable
        except:
            print ("Configuration file error: missing variables")
            exit(1)
    
    count_unstructured = 0
    count_tot = 0
    print (OUTDIR + "output_" + source)
    if not debugmode: output_file = open(OUTDIR + "output_" + source,'w')

    # while count_source < lines[source]*0.01 and (not features_needed <= 0) : 
    feat_appear = {}
    for file in sourcepath:
        feat_appear[file] = []    

        if file.endswith('.gz'):
            input_file = gzip.open(file,'r')
        else:
            input_file = open(file,'r')

        line = input_file.readline()


        # First read to generate list of number of appearances
        if line:
            log = ""     
            while line:
                log += line 
    
                if len(log.split(config['RECORD_SEPARATOR'][source])) > 1:
                    logExtract = log.split(config['RECORD_SEPARATOR'][source])[0]
                    
                    # For each log, extract timestamp with regular expresions and check if it is in the 
                    # input timestamps
                    try:

                        t = getUnstructuredTime(logExtract, VARIABLES[timearg]['where'], config['TSFORMAT'][source])                    
                        if str(t).strip() in formated_timestamps:    
                            # Check if features appear in the log to write in the file.
                            record = faac.Record(logExtract,config['SOURCES'][source]['CONFIG']['VARIABLES'], config['STRUCTURED'][source], config['TSFORMAT'][source], config['All'])
                            obs = faac.Observation.fromRecord(record, FEATURES_sel)
                            feat_appear[file].append(sum( [obs.data[i].value for i in range(len(obs.data))]))
                    except:
                        pass
                        
                    log = ""
                    for n in logExtract.split(config['RECORD_SEPARATOR'][source])[1::]:
                        log += n
                line = input_file.readline()

            # Deal with the last log, not processed during while loop.
            log += line
            try:                                
                t = getUnstructuredTime(log, VARIABLES[timearg]['where'], config['TSFORMAT'][source])
                if str(t) in timestamps:
                    record = faac.Record(logExtract,config['SOURCES'][source]['CONFIG']['VARIABLES'], config['STRUCTURED'][source], config['TSFORMAT'][source], config['All'])
                    obs = faac.Observation.fromRecord(record, FEATURES_sel)
                    feat_appear[file].append(sum( [obs.data[i].value for i in range(len(obs.data))]))
            except:
                pass

        input_file.close()

    # Obtain number of features needed to extract the log
    features_needed = len(depars_features)
    count = 0
    while count < int(threshold) and (not features_needed <= 1):
        for file in feat_appear:
            count += feat_appear[file].count(int(features_needed))

        print("There are " + str(count) + " unstructured logs with more than " + str(features_needed) + " matching features...")
        features_needed -= 1

    # Re-read the file
    for file in sourcepath:
        index = 0

        if file.endswith('.gz'):
            input_file = gzip.open(file,'r')
        else:
            input_file = open(file,'r')

        input_file.seek(0)
        line = input_file.readline()
            
        if line:
            log = "" + line     
            while line:
                log += line 
                if len(log.split(config['RECORD_SEPARATOR'][source])) > 1:
                    count_tot += 1    
                    logExtract = log.split(config['RECORD_SEPARATOR'][source])[0]
                    
                    # For each log, extract timestamp with regular expresions and check if it is in the 
                    # input timestamps
                    try:
                        t = getUnstructuredTime(logExtract, VARIABLES[timearg]['where'], config['TSFORMAT'][source])                                                
                        if str(t).strip() in formated_timestamps:    
                            # Check if features appear in the log to write in the file.
                            if not debugmode and feat_appear[file][index] > features_needed:
                                output_file.write(logExtract + config['RECORD_SEPARATOR'][source])
                                count_unstructured += 1    
                            index += 1
                    except:
                        pass

                    log = ""
                    for n in logExtract.split(config['RECORD_SEPARATOR'][source])[1::]:
                        log += n
                line = input_file.readline()

        input_file.close()
    if not debugmode: output_file.close()
    return (count_unstructured, count_tot)


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


def format_timestamps(timestamps, source_format):
    '''
    Format a list of timestamps (with t_format) to the data source timestamp format (source_format)
    '''
    
    timestamps_formated= []
    t_format = "%Y-%m-%d %H:%M:%S"   # timestamp format for timestamps in deparsing_input file

    for t in timestamps:
        timestamps_formated.append(str(datetime.strptime(t, t_format).strftime(source_format)))

    return timestamps_formated


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


def getUnstructuredTime (log, patern, dateFormat):
    '''
    # Fuction to extract timestamp from an unstructured source
    '''
    p = re.search(patern,log)
    try:
        date_string = p.group(0)
        d = datetime.strptime(date_string,dateFormat)
        d = d.replace(second = 00)
        
        return d.strftime(dateFormat)

    except:
        return None


def getStructuredTime(line, pos, dateFormat):
    '''
    # Fuction to extract timestamp from an structured source
    '''

    valueList = line.split(',')
    rawTime = valueList[pos]
    time = datetime.strptime(rawTime, dateFormat)
    time = time.replace(second = 00)                # ignore seconds
    time = time.replace(microsecond = 00)           # ignore microseconds
    
    return time.strftime(dateFormat)


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


def getConfiguration(config_file):
    '''
    Function to extract configurations from yaml files. 
    This info is stored into a dictionary.
    '''

    stream = open(config_file, 'r')
    conf = yaml.safe_load(stream) # conf = yaml.load(stream)
    stream.close()
    return conf


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
        print('\033[33m'+"Loading FCdeparser... Run program in debug mode with -d option in order to check the feature selection criteria"+'\033[m')
        print ("\n-------------------------------- FCDEPARSER -------------------------------")
         
    print("* Loaded Deparsing input file."+'\033[m')
    print("- Features to search: %s" %(deparsInput['features']))
    if deparsInput['timestamps'] and debugmode:
        print("- In logs with timestamps: %s" %(deparsInput['timestamps']))
    else:
        print("- In any log (not specified timestamps)")
    
    return  

    
if __name__ == "__main__":
    
    if version_info[0] != 3:
        print('\033[31m'+ "** PYTHON VERSION ERROR **" +'\033[m')
        print("Please, use python3 to run this program")
        exit(1)
        
    main()
