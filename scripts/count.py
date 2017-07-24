#!/usr/bin/env python

import argparse
import re

def main():
	args = get_arguments()
	col = int(args.col)

	print "----------------------------------------------------"
	print "col = %d" %(col)
	print "val = %s" %(args.val)
	print "----------------------------------------------------"


	fileCount = 0
	outstream = open(args.output, 'w')
	for inpath in args.files:
		stream = open(inpath, 'r')
		fileCount += 1
		valueCount = 0
		lineCount = 0
		line = stream.readline()
		while line:
			lineCount += 1
			fieldList = line.split(',')
			value = fieldList[col]
			if value == args.val:
				valueCount += 1
			line = stream.readline()
		outstream.write(getTag(inpath) + ', ' + str(valueCount) + '\n')

		stream.close()
		print "#%s / %s << %s: %d / %d" %(fileCount, len(args.files), inpath, valueCount, lineCount)
				
	print "----------------------------------------------------"
	print "%d input files" %(fileCount)
	

	outstream.close()
	print "Written >> %s" %(args.output)
	
	

def getTag(filename):
	tagSearch = re.search("(\w*)\.\w*$", filename)
	if tagSearch:
		return tagSearch.group(1)
	else:
		return None


def get_arguments():
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
	description='''Count the number of occurences of a given event in the data.''')
	parser.add_argument('-o','--output', metavar='OUTPUT', default='count_result.dat', help='Output file. Default: "count_result.dat".')
	parser.add_argument('-c','--col', metavar='COLUMN', default=0, help='Column (order) of the field to count. Default: 0')

	parser.add_argument('-v','--val', metavar='VALUE', help='Value corresponding to the event to count.')

	parser.add_argument('files', metavar='FILE', nargs='+',help='Input data files (CSV format)')
	args = parser.parse_args()
	return args

if __name__ == "__main__":
	main()

