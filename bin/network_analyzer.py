#!/usr/bin/env python
###############################################################################
#                                                                             #
# This program is free software: you can redistribute it and/or modify        #
# it under the terms of the GNU General Public License as published by        #
# the Free Software Foundation, either version 3 of the License, or           #
# (at your option) any later version.                                         #
#                                                                             #
# This program is distributed in the hope that it will be useful,             #
# but WITHOUT ANY WARRANTY; without even the implied warranty of              #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the                #
# GNU General Public License for more details.                                #
#                                                                             #
# You should have received a copy of the GNU General Public License           #
# along with this program. If not, see <http://www.gnu.org/licenses/>.        #
#                                                                             #
###############################################################################
 
__author__ = "Joel Boyd"
__copyright__ = "Copyright 2015"
__credits__ = ["Joel Boyd"]
__license__ = "GPL3"
__version__ = "0.0.1"
__maintainer__ = "Joel Boyd"
__email__ = "joel.boyd near uq.net.au"
__status__ = "Development"
 
###############################################################################

from kegg_matrix import KeggMatrix
from network_builder import NetworkBuilder
import argparse
import logging
import os
import sys

debug={1:logging.CRITICAL,
       2:logging.ERROR,
       3:logging.WARNING,
       4:logging.INFO,
       5:logging.DEBUG}

###############################################################################

def check_args(args):
    if args.subparser_name==NetworkAnalyser.EXPLORE:
        if not(args.queries):
            if args.depth:
                logging.warning("--depth argument ignored without --queries \
flag")
    if args.subparser_name==NetworkAnalyser.PATHWAY:
        pathway_opts = [args.from_node, args.to_node, args.filter, args.limit]
        if not any(pathway_opts):
            raise Exception("No options provided to pathway. Please pass an \
argument to one of the following flags:\n%s" % ('\n'.join(['--from_node',
                                                           '--to_node',
                                                           '--filter',
                                                           '--queries\n'])))

    if(os.path.isfile(args.output_prefix + NetworkAnalyser.NETWORK_SUFFIX) or
       os.path.isfile(args.output_prefix + NetworkAnalyser.METADATA_SUFFIX)):
        if args.force:
            logging.warning("Removing existing file with name: %s" \
                                                        % args.output_prefix)
            if os.path.isfile(args.output_prefix + 
                              NetworkAnalyser.NETWORK_SUFFIX):
                os.remove(args.output_prefix + NetworkAnalyser.NETWORK_SUFFIX)
            if os.path.isfile(args.output_prefix + 
                              NetworkAnalyser.METADATA_SUFFIX):
                os.remove(args.output_prefix + NetworkAnalyser.METADATA_SUFFIX)
        else:
            raise Exception("File %s exists" % args.output_prefix)
        
class CustomHelpFormatter(argparse.HelpFormatter):
    def _split_lines(self, text, width):
        return text.splitlines()
    
def phelp():
    print u"""
    KEGG_network_analyzer
===============================================================================
J. Boyd

The idea is simple: construct metabolic networks from your metagenomic and/or 
transcriptomic data using the KEGG database as a framework.

KEGG_network_analyzer allows you to look at specific pathways in KEGG, and to 
explore possible pathways from a given metabolite. 


    Subcommands
-------------------------------------------------------------------------------
    network - Construct the entire metabolic network an input matrix
    
    explore - Start from specified query compounds and make steps into 
              metabolism. Answer questions like "How is glucose metabolized in 
              my sample?" or "How many pathways are used to produce methane?"
              
    pathway - Specify paths in metabolism to explore. UNDER DEVELOPMENT.
    
"""

class NetworkAnalyser:
    NETWORK         = 'network'
    EXPLORE         = 'explore'
    DEGRADE         = 'degrade'
    PATHWAY         = 'pathway'
    NETWORK_SUFFIX  = '_network.tsv'
    METADATA_SUFFIX = '_metadata.tsv'
    
    def __init__(self, metadata):
        self.metadata = {}
        for line in open(metadata):
            sample_id, group = line.strip().split('\t')
            if group in self.metadata:
                self.metadata[group].append(sample_id)
            else:
                self.metadata[group] = [sample_id]

    def _write_results(self, output_path, output_lines):
        '''
        Parameters
        ----------
        output_path: string
            Path to non-existent file to write output lines to
        output_lines: list
            list containing lines to write to output path
        '''
        logging.info('Writing results to file: %s' % output_path)
        with open(output_path, 'w') as output_path_io: 
            output_path_io.write('\n'.join(output_lines))
            output_path_io.flush()
        
    def main(self, args):
             #matrix_path, queries, depth, transcriptome, output):
        '''
        Parameters
        ----------
        matrix_path: string
            Path to file containing a KO matrix build from either metagenomic
            or metatranscriptomic data.
        queries: string
            Path to file containing query compounds
        depth: integer
            Number of steps into metabolism to take if 'queries' is provided
        transcriptome: string
            Path to file containing a KO matrix of transcriptomic data
        '''
        
        nb = NetworkBuilder(self.metadata.keys())
        km = KeggMatrix(args.matrix, args.transcriptome)

        abundances_metagenome = \
                {key:km.group_abundances(self.metadata[key],
                                         km.reaction_matrix) 
                 for key in self.metadata.keys()}

        if args.transcriptome:
            abundances_transcriptome = \
                    {key:km.group_abundances(self.metadata[key],
                                             km.reaction_matrix_transcriptome) 
                     for key in self.metadata.keys()}            
            abundances_expression = \
                    {key:km.group_abundances(self.metadata[key],
                                             km.reaction_matrix_expression) 
                     for key in self.metadata.keys()}

        else:
            abundances_transcriptome = None
            abundances_expression    = None

        if args.subparser_name==self.NETWORK:
            logging.info("Constructing entire metabolic network. Be patient.")
            network_lines, node_metadata = \
                            nb.all_matrix(abundances_metagenome,
                                          abundances_transcriptome,
                                          abundances_expression)
        elif args.subparser_name==self.EXPLORE:
            logging.info("Using supplied queries (%s) to explore network" \
                                                    % args.queries)
            network_lines, node_metadata = \
                            nb.query_matrix(abundances_metagenome, 
                                            abundances_transcriptome,
                                            abundances_expression,
                                            args.queries,
                                            args.depth)
        elif args.subparser_name==self.PATHWAY:
            network_lines, node_metadata = \
                            nb.pathway_matrix(abundances_metagenome, 
                                              abundances_transcriptome,
                                              abundances_expression,
                                              args.limit,
                                              args.filter,
                                              args.from_node,
                                              args.to_node,
                                              args.anabolic,
                                              args.catabolic,
                                              args.bfs_shortest_path)

        self._write_results(args.output_prefix + self.NETWORK_SUFFIX, network_lines)
        self._write_results(args.output_prefix + self.METADATA_SUFFIX, node_metadata)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help="--", dest='subparser_name')
    
    #~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#
    #~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#
    base = argparse.ArgumentParser(add_help=False)
    
    base_input_options = base.add_argument_group('Input options')
    base_input_options.add_argument('--matrix', required=True,
                                    help='KO matrix. REQUIRED.')
    base_input_options.add_argument('--metadata', required=True,
                                    help='Description of samples. REQUIRED.')
    base_input_options.add_argument('--transcriptome', 
                                    help='Transcriptome to ko matrix.')
    
    base_network_options = base.add_argument_group('Network options')
    base_network_options.add_argument('--rpair', action='store_true',
                                      help='Use rpair to construct network, \
instead of the reaction database')
    
    base_output_options = base.add_argument_group('Output options')
    base_output_options.add_argument('--output_prefix', default = 'network_analyser_output',
                                     help='Output file')
    base_output_options.add_argument('--force', action='store_true',
                                     help='Overwrite previous run')
    
    base_logging_options = base.add_argument_group('Logging options')
    base_logging_options.add_argument('--log',
                                      help='output logging information to \
this file.')
    base_logging_options.add_argument('--verbosity', type = int, default = 4,
                                      help='Level of verbosity \
(1 - 5 - default = 4) 5 = Very verbose, 1 = Silent')
    
    #~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#
    #~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#
    network = subparsers.add_parser('network',
                                    formatter_class=CustomHelpFormatter,
                                    parents=[base])
    
    #~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#
    #~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#
    explore = subparsers.add_parser('explore',
                                    formatter_class=CustomHelpFormatter,
                                    parents=[base])
        
    explore_query_options = explore.add_argument_group('Query options')
    explore_query_options.add_argument('--queries', required=True,
                                       help='query compounds')
    explore_query_options.add_argument('--depth', type=int, default=2,
                                       help='depth')

    #~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#
    #~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#
    pathway = subparsers.add_parser('pathway',
                                    formatter_class=CustomHelpFormatter,
                                    parents=[base])

    pathway_pathway_options = pathway.add_argument_group('Pathway options')
    pathway_pathway_options.add_argument('--limit', default=[], nargs='+',
                                       help='USE ONLY these reactions, or \
reactions within this pathway or module (space separated list).')
    pathway_pathway_options.add_argument('--filter', default=[], nargs='+',
                                       help='Do not use these reactions, or \
reactions within this pathway or module (space separated list).')
    pathway_pathway_options.add_argument('--from_node', 
                                       help='Find path from this node to the \
node specified to --to_node. UNDER DEVELOPMENT.')
    pathway_pathway_options.add_argument('--to_node',
                                       help='Find path to this node from the \
node specified to --from_node. UNDER DEVELOPMENT.')
    pathway_pathway_options.add_argument('--bfs_shortest_path', 
                                         action='store_true',
                                         help="Find shortest path using a \
breadth first search (DFS) instead of the default weighted dijkstra's \
algorithm. UNDER DEVELOPMENT.")
    pathway_directionality_options = \
                        pathway.add_argument_group('Directionality options')
    pathway_directionality_options\
                        .add_argument('--catabolic', action='store_true',
                                       help='Find degradation pathway. \
NOT IMPLEMENTED.')
    pathway_directionality_options\
                        .add_argument('--anabolic', action='store_true',
                                      help='Find assimilation pathway. \
NOT IMPLEMENTED.')
    
    #~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#
    #~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#
    if(len(sys.argv) == 1 or sys.argv[1] == '-h' or sys.argv[1] == '--help'):
        phelp()
    else:
        args = parser.parse_args()
        if args.log:
            if os.path.isfile(args.log): 
                raise Exception("File %s exists" % args.log)
            logging.basicConfig(filename=args.log, level=debug[args.verbosity], 
                                format='%(asctime)s %(levelname)s: %(message)s', 
                                datefmt='%m/%d/%Y %I:%M:%S %p')
        else:
            logging.basicConfig(level=debug[args.verbosity], 
                                format='%(asctime)s %(levelname)s: %(message)s', 
                                datefmt='%m/%d/%Y %I:%M:%S %p')
        
        check_args(args)
        
        na=NetworkAnalyser(args.metadata)
        na.main(args)