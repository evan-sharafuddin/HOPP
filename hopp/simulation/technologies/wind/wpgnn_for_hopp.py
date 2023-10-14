# Implements WPGNN model for HOPP
# Adapted from example_opt and wpgnn_demo
# https://github.com/NREL/WPGNN

# TODO create a pip installable project for WPGNN 
# from WPGNN.wpgnn import WPGNN
# from WPGNN import utils

import csv
import numpy as np

from floris.tools import FlorisInterface

from hopp.simulation.base import BaseClass
from hopp.simulation.technologies.sites import SiteInfo
from hopp.type_dec import resource_file_converter

class WPGNNForHOPP(WPGNN): 
    '''
        Parameters:
            w_init - Sonnet initializer object for network weights
            b_init - Sonnet initializer object for network biases
            eN_in, eN_out - number of input/output edge features
            nN_in, nN_out - number of input/output  node features
            gN_in, gN_out - number of input/output  graph features
            n_layers - number of graph layers in the network
            graph_layers - list of graph layers 
            model_path - location of a save model, if None then just use random weight initialization
            scale_factors - list of scaling factors used to normalize data
            optmizer - Sonnet optimizer object that will be used for training
    '''
    
    def __init__(self, farm_config, site, eN=2, nN=3, gN=3, graph_size=None,
                       scale_factors=None, model_path=None, name=None):    
        
        # initialize model (not sure if inheretance is needed here)
        self.model = super(WPGNNForHOPP, self).__init__(eN, nN, gN, graph_size, scale_factors, model_path, name)
        self.config_dict = farm_config
        self.site = site

        # get wind resource data
        self.wind_resource_data = self.site.wind_resource.data
        self.num_simulations = len(self.wind_resource_data['data'])
        self.speeds, self.wind_dirs = self.parse_resource_data()


    def parse_resource_data(self):
        # NOTE copied this from FLORIS
        # extract data for simulation
        speeds = np.zeros(len(self.wind_resource_data['data']))
        wind_dirs = np.zeros(len(self.site.wind_resource.data['data']))
        data_rows_total = 4

        # seems to be combining data from the two heights 
        if np.shape(self.site.wind_resource.data['data'])[1] > data_rows_total:
            height_entries = int(np.round(np.shape(self.site.wind_resource.data['data'])[1]/data_rows_total))
            data_entries = np.empty((height_entries))
            for j in range(height_entries):
                data_entries[j] = int(j*data_rows_total)
            data_entries = data_entries.astype(int)
            for i in range((len(self.site.wind_resource.data['data']))):
                data_array = np.array(self.site.wind_resource.data['data'][i])
                speeds[i] = np.mean(data_array[2+data_entries])
                wind_dirs[i] = np.mean(data_array[3+data_entries])
        else:
            for i in range((len(self.site.wind_resource.data['data']))):
                speeds[i] = self.site.wind_resource.data['data'][i][2]
                wind_dirs[i] = self.site.wind_resource.data['data'][i][3]

        return speeds, wind_dirs
    
    def execute(self):
        print('Simulating wind farm output in WPGNN...')

        # generate plant layout 
        generator = PLayGen()
        wind_plant = generator()
        # set yaw angles for each turbine to zero
        yaw_angles = np.zeros(wind_plant.shape[0], 1)
        # TODO leaving this as the value set in the WPGNN example
        turb_intensity = 0.08

        # Create list of graphs (one for each hour)
        input_graphs = []
        for i in range(self.num_simulations):
            uv = utils.speed_to_velocity([self.speeds[i], self.wind_dirs[i]]) # converts speeds to vectors?
            edges, senders, receivers = utils.identify_edges(wind_plant, self.wind_dirs[i])
            input_graphs.append({'globals': np.array([uv[0], uv[1], turb_intensity]),
                                'nodes': np.concatenate((wind_plant, yaw_angles), axis=1),
                                'edges': edges,
                                'senders': senders,
                            'receivers': receivers})
            
        # Should have 8760 graphs 
        print(f"Number of graphs created: {len(input_graphs)}")

        # Evaluate model

        plant_power = [] # total wind plant output, hourly time series
        for i in range(len(input_graphs))
            normed_input_graph, _ = utils.norm_data(xx=input_graphs[i], scale_factors=self.scale_factors)
            normed_output_graph = graphs_tuple_to_data_dicts(self.model(data_dicts_to_graphs_tuple(normed_input_graph)))
            output_graph = utils.unnorm_data(ff=normed_output_graph, scale_factors=self.scale_factors)
            plant_power.append()
