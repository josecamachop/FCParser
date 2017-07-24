#!/usr/bin/env python

import argparse
import sys
import os
from datetime import (datetime, timedelta)


def main():
	args = getArguments()
	
	if args.value:
		target = args.value
	else:
		target = getDefaultValue(args.files, args.col)

	print "Field: %s" %(args.col)
	print "Value: %s" %(target)
	print "Outdir: %s" %(args.outdir)
	
	for fin in args.files:
		fout = getOutFilename(fin, args.ending, args.outdir)
		
		instream  = open(fin, 'r')
		outstream = open(fout,'w')
		line = instream.readline()
		lineCount = 0
		matchCount = 0
		while line:
			lineCount += 1
			valueList = line.split(',')
			value = valueList[args.col]
			if value == target:
				outstream.write(line)
				matchCount += 1
			line = instream.readline()
		instream.close()
		outstream.close()
		
		print "%s >> %s (%s / %s lines)" %(os.path.split(fin)[1], os.path.split(fout)[1], matchCount, lineCount)
		
	
	
def getOutFilename(infile, suffix, outdir):
	(head, tail) = os.path.split(infile)
	(root, ext) = os.path.splitext(tail)
	if outdir:
		if not outdir.endswith('/'):
			outdir = outdir + '/'
		outfile = outdir + root + '-' + suffix + ext
	else:
		outfile = head + '/' + root + '-' + suffix + ext
	return outfile

	
def getDefaultValue(fileList, col):
	try:
		stream = open(fileList[0])
		line = stream.readline()
		stream.close()
		valueList = line.split(',')
		value = valueList[col]
	except:
		print "Warning: value set to None"
		value = None
	return value

def getArguments():
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
	description='''Filter datasource.\nSelect records where the field COLUMN equals VALUE, and write them in OUTPUT.''')
	parser.add_argument('-c','--col', metavar='COLUMN', type=int, default=0, help='Column (order) of the field to filter. Default: 0.')
	parser.add_argument('-v','--value', metavar='VALUE', help='Value used to filter. Default: Use the value of the first record.')
	parser.add_argument('files', metavar='FILES', nargs='+',help='Input data file (CSV format).')
	parser.add_argument('-e','--ending', metavar='SUFFIX', default='filtered',help="Suffix appended to create each output file name. Default: 'filtered'.")
	parser.add_argument('-o','--outdir', metavar='OUTDIR', help="Directory to write the output. Default: Use the input file directory.")
	args = parser.parse_args()
	return args

if __name__ == "__main__":
	main()

