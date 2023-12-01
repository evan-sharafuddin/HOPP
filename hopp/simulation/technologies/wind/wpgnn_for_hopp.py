# Implements WPGNN model for HOPP
# Adapted from example_opt and wpgnn_demo
# https://github.com/NREL/WPGNN

# TODO create a pip installable project for WPGNN 
# from WPGNN.wpgnn import WPGNN
# from WPGNN import utils

import csv
import numpy as np
import yaml
from tqdm import tqdm
import matplotlib.pyplot as plt

# from floris.tools import FlorisInterface

from hopp.simulation.base import BaseClass
from hopp.simulation.technologies.sites import SiteInfo
from hopp.type_dec import resource_file_converter

from wpgnn.wpgnn import WPGNN
from wpgnn.playgen import PLayGen
from wpgnn import utils

from graph_nets.utils_tf import *
from graph_nets.utils_np import graphs_tuple_to_data_dicts

from floris.tools import FlorisInterface

class WPGNNForHOPP(): 
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
    
    def __init__(self, site, farm_config, eN=2, nN=3, gN=3, graph_size=None,
                       scale_factors=None, model_path=None, name=None):    
        
        # initialize model
        self.model = WPGNN(eN, nN, gN, graph_size, scale_factors, model_path, name)
        self.config = farm_config
        self.site = site

        floris_input_file = self.config.floris_config

        if floris_input_file is None:
            raise ValueError("A floris configuration must be provided")
        if self.config.timestep is None:
            raise ValueError("A timestep is required.")
        
        # for now using FI To pull data...
        self.fi = FlorisInterface(floris_input_file)
        self._timestep = self.config.timestep

        # get wind resource data
        self.wind_resource_data = self.site.wind_resource.data
        self.num_simulations = len(self.wind_resource_data['data'])
        self.speeds, self.wind_dirs = self.parse_resource_data()

        self.wind_farm_xCoordinates = self.fi.layout_x
        self.wind_farm_yCoordinates = self.fi.layout_y
        self.nTurbs = len(self.wind_farm_xCoordinates)
        self.turb_rating = self.config.turbine_rating_kw
        self.wind_turbine_rotor_diameter = self.fi.floris.farm.rotor_diameters[0]
        self.system_capacity = self.nTurbs * self.turb_rating

        self.wind_turbine_powercurve_powerout = [1] * 30    # dummy for now

        # results
        self.gen = []
        self.annual_energy = None
        self.capacity_factor = None

    def value(self, name: str, set_value=None):
        """
        if set_value = None, then retrieve value; otherwise overwrite variable's value
        """
        if set_value:
            self.__setattr__(name, set_value)
        else:
            return self.__getattribute__(name)

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
    
    def execute(self, project_life):
        print('Simulating wind farm output in WPGNN...')

        # generate plant layout 
        # generator = PLayGen(N_turbs=self.nTurbs)
        # wind_plant = generator()

        # generate plant layout manually (taken from floris config file)
        wind_plant = np.array([[0.0, 0.0], [630.0, 0.0], [1260.0, 0.0], [1800.0, 0.0]])
        
        # UNCOMMENT TO PLOT WINDPLANT
        # plt.figure(figsize=(4, 4))
        # plt.scatter(wind_plant[:, 0], wind_plant[:, 1], s=15, facecolor='b', edgecolor='k')
        # xlim = plt.gca().get_xlim()
        # ylim = plt.gca().get_ylim()
        # plt.xlim(np.minimum(xlim[0], ylim[0]), np.maximum(xlim[1], ylim[1]))
        # plt.ylim(np.minimum(xlim[0], ylim[0]), np.maximum(xlim[1], ylim[1]))
        # plt.gca().set_aspect(1.)
        # plt.title('Number of Turbines: {}'.format(wind_plant.shape[0]))
        # plt.show()

        # set yaw angles for each turbine to zero
        yaw_angles = np.zeros((wind_plant.shape[0], 1)) 

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

        # Evaluate model (can evaluate as batch)
        normed_input_graph, _ = utils.norm_data(xx=input_graphs, scale_factors=self.model.scale_factors)
        normed_output_graph = graphs_tuple_to_data_dicts(self.model(data_dicts_to_graphs_tuple(normed_input_graph)))
        output_graph = utils.unnorm_data(ff=normed_output_graph, scale_factors=self.model.scale_factors)

        # extract plant power time series
        plant_power = [output_graph[i]['globals'][0] for i in range(len(output_graph))]
        self.gen = plant_power

        # TODO confirm units
        self.annual_energy = sum(plant_power)
        print(f"Annual energy output (MWh): {self.annual_energy/1e6}")

        self.capacity_factor = self.annual_energy/1e6 / (8760 * self.system_capacity/1e3) * 100
        print(f"Plant capacity factor (MWh/MWh): {self.capacity_factor}")

        
        # calculate values with PySAM losses
        annual_energy_corr = self.annual_energy * ((100 - 12.83)/100) / 1e6
        capacity_factor_corr = annual_energy_corr / (8760 * self.system_capacity/1e3) * 100
        print(f"Annual energy output (w/ PySAM correction factors) (MWh): {annual_energy_corr}")
        print(f"Plant capacity factor (w/ PySAM correction factors) (MWh/MWh): "
              f"{capacity_factor_corr}")