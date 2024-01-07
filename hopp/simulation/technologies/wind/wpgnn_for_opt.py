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

from hopp.simulation.technologies.wind.power_to_h2 import get_lcoh

# example_opt imports
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import numpy as np
import tensorflow as tf
tf.get_logger().setLevel('ERROR')
from wpgnn.wpgnn import WPGNN
from scipy import optimize
import tensorflow as tf
from graph_nets.utils_tf import *
from graph_nets.utils_np import graphs_tuple_to_data_dicts
import wpgnn.utils

import matplotlib.pyplot as plt

# numpy API on tensorflow
import tensorflow.experimental.numpy as tnp
tnp.experimental_enable_numpy_behavior()

class WPGNNForOpt(): 
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

        # TODO use yaml here instead?
        # self.wind_farm_xCoordinates = self.fi.layout_x
        # self.wind_farm_yCoordinates = self.fi.layout_y
        # self.nTurbs = len(self.wind_farm_xCoordinates)

        self.domain = np.array([[-1000., 1000.],
                        [-1000., 1000.]]) # in m, hardcoded for now (TODO transition to using site verts in yaml?)
        self.nTurbs = 4 # TODO hardcoded

        # self.x = poisson_disc_samples(self.nTurbs, self.domain, R=[250., 350.])
        self.x = np.array([[0.0, 0.0], [630.0, 0.0], [1260.0, 0.0], [1800.0, 0.0]])

        # plt.figure(figsize=(4, 4))
        # plt.scatter(self.x[:, 0], self.x[:, 1], s=15, facecolor='b', edgecolor='k')
        # xlim = plt.gca().get_xlim()
        # ylim = plt.gca().get_ylim()
        # plt.xlim(np.minimum(xlim[0], ylim[0]), np.maximum(xlim[1], ylim[1]))
        # plt.ylim(np.minimum(xlim[0], ylim[0]), np.maximum(xlim[1], ylim[1]))
        # plt.gca().set_aspect(1.)
        # plt.title('Number of Turbines: {}'.format(self.x.shape[0]))
        # plt.show()

        self.ti = 0.08 # turbulance intensity

        # get wind resource data
        self.wind_resource_data = self.site.wind_resource.data
        self.num_simulations = len(self.wind_resource_data['data'])
        self.ws, self.wd = self.parse_resource_data()
        # self.yaw = np.zeros((self.nTurbs, self.wd.size))
        self.yaw = np.zeros((self.x.shape[0], 1)) # choose this for the yaw because not using wind rose

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
    
    # use inside of wind_plant
    def opt(self): 
        N_turbs = self.nTurbs
        yaw = self.yaw

        domain = self.domain

        A = np.eye(N_turbs*2)
        lb = np.repeat(np.expand_dims(domain[:, 0], axis=0), N_turbs, axis=0).reshape((-1, ))
        ub = np.repeat(np.expand_dims(domain[:, 1], axis=0), N_turbs, axis=0).reshape((-1, ))
        domainConstraint = optimize.LinearConstraint(A, lb, ub)

        # currently not using yaw
        spacing_constraint = {'type': 'ineq', 'fun': spacing_func, 'args': [0, 250.]}

        A = np.eye(self.nTurbs*2)
        lb = np.repeat(np.expand_dims(self.domain[:, 0], axis=0), N_turbs, axis=0).reshape((-1, ))
        ub = np.repeat(np.expand_dims(self.domain[:, 1], axis=0), N_turbs, axis=0).reshape((-1, ))
        domain_constraint = optimize.LinearConstraint(A, lb, ub)

        constraints = [spacing_constraint, domain_constraint]

        # again, currently not using yaw
        result = optimize.minimize(self.objective_noYaw,  self.x.reshape((-1, )),
                                    args=(yaw, self.ws, self.wd, self.ti, self.model),
                                    method='SLSQP', jac=True,
                                    constraints=constraints)
        
        return result
    
    def objective_noYaw(self, x, yaw, ws, wd, ti, model):
        x = x.reshape((-1, 2))
        n_turbines = x.shape[0]

        # Create list of graphs (one for each hour)
        input_graphs = []
        for i in range(self.num_simulations):
            uv = utils.speed_to_velocity([self.ws[i], self.wd[i]]) # converts speeds to vectors?
            edges, senders, receivers = utils.identify_edges(x, wd[i])
            input_graphs.append({'globals': np.array([uv[0], uv[1], ti]),
                                'nodes': np.concatenate((x, yaw), axis=1),
                                'edges': edges,
                                'senders': senders,
                                'receivers': receivers})
            
            
        
        normed_input_graphs, _ = utils.norm_data(xx=input_graphs, scale_factors=self.model.scale_factors)
        x_graph_tuple = data_dicts_to_graphs_tuple(normed_input_graphs)

        # out_graph = graphs_tuple_to_data_dicts(self.model(x_graph_tuple))
        # plant_power_test3 = [5e8 * out_graph[i]['globals'][0] for i in range(len(out_graph))] # seeing what tf.Variable does, if it makes a change

        x_graph_tuple = x_graph_tuple.replace(nodes=tf.Variable(x_graph_tuple.nodes))

        # plant_power_test = 5e8*self.model(x_graph_tuple).globals[:, 0] # unnorming result, NOTE in example_opt divided by 1e6 to convert to MW 
        
        # out_graph = graphs_tuple_to_data_dicts(self.model(x_graph_tuple))
        # plant_power_test2 = [5e8 * out_graph[i]['globals'][0] for i in range(len(out_graph))] # using logic from wpgnn_for_hopp

        LCOH, dLCOH = self.eval_model(x_graph_tuple)

        dLCOH = dLCOH.numpy()/np.array([[75000., 85000., 15.]])
        dLCOH = np.sum(dLCOH.reshape((wd.size, ws.size, x.shape[0], 3)), axis=(0, 1))[:, :2].reshape((-1, ))

        return LCOH.numpy(), dLCOH
    
    # @tf.function
    def eval_model(self, x_graph_tuple):
        
        with tf.GradientTape(persistent=True) as tape:
            tape.watch(x_graph_tuple.nodes)

            plant_power = 5e8*self.model(x_graph_tuple).globals[:, 0] # unnorming result, units of power W 
            LCOH = get_lcoh(plant_power)
            
            ########## test gradients
            # print('\n\n\nBEGIN TESTS')
            # # 1) should definitely work
            # test1 = sum(plant_power[:100])
            # jac1 = tape.jacobian(test1, x_graph_tuple.nodes)

            # print(jac1.shape) # works

            # # 2) using numpy operations... not sure if it will work
            # import tensorflow.experimental.numpy as np
            # np.experimental_enable_numpy_behavior()
            # test2 = np.sum(plant_power[:100])
            # jac2 = tape.jacobian(test2, x_graph_tuple.nodes)

            # print(jac2.shape) # works

            # 3) nested functions using numpy operations
            # def fun2(input):
            #     import tensorflow.experimental.numpy as np
            #     np.experimental_enable_numpy_behavior()
            #     input *= input
            #     input = input + 5.129035234
            #     return input
            
            # def fun1(input):
            #     import tensorflow.experimental.numpy as np
            #     np.experimental_enable_numpy_behavior()
            #     return fun2(input) + np.zeros(input.shape)
            
            # import tensorflow.experimental.numpy as np
            # np.experimental_enable_numpy_behavior()

            # test3 = plant_power[:100]
            # test3 = np.sum(fun1(test3))
            # jac3 = tape.jacobian(test3, x_graph_tuple.nodes)

            # print(jac3.shape)

            # test4 = plant_power[:100]
            # dict_stuff = {'test4': test4, 'pp': 12}
            # test4 = np.sum(dict_stuff['test4'] * dict_stuff['pp'])

            # jac4 = tape.jacobian(test4, x_graph_tuple.nodes)
            # print(jac4.shape)

            # print('END TESTS\n\n\n')
            ########## END TEST GRADIENTS


        print('evalulating gradient...')

        dLCOH = tape.jacobian(LCOH, x_graph_tuple.nodes)
        print(type(dLCOH))



        # print('evaluating gradient...')
        # dpower_dnodes = tape.jacobian(plant_power, x_graph_tuple.nodes)
        # print(dpower_dnodes.shape)
        # plant_power, dpower_dnodes = self.find_plant_power(x_graph_tuple) # plant_power in W

        
        # from jax import jacfwd # TODO might want to use jacrev, see documentation

        # dLCOH_dpower = jacfwd(get_lcoh)(plant_power)

        # dLCOH = dLCOH_dpower * dpower_dnodes

        return LCOH, dLCOH
    
    # @tf.function
    # def find_plant_power(self, x_graph_tuple):
    #     with tf.GradientTape() as tape:
    #         tape.watch(x_graph_tuple.nodes)

    #         plant_power = 5e8*self.model(x_graph_tuple).globals[:, 0] # unnorming result, NOTE in example_opt divided by 1e6 to convert to MW 

    #         # # from past debugging... this should never be triggered
    #         # if max(plant_power) == 0:
    #         #     raise Exception("WPGNN evaluated to plant power output of zero...")

    #     print('evaluating gradient...')
    #     dpower_dnodes = tape.jacobian(plant_power, x_graph_tuple.nodes)
    #     print(dpower_dnodes.shape)
        
    #     return plant_power, dpower_dnodes
    

# had to move this out of the class decleration for some reason
def spacing_func(x, n_windDirs=0, min_spacing=250.):
    '''used as constraint in the optimization problem'''

    x = x.reshape((-1, 2+n_windDirs))[:, :2]

    D = np.sqrt(np.sum((np.expand_dims(x, axis=0) - np.expand_dims(x, axis=1))**2, axis=2))

    r = np.arange(D.shape[0])
    mask = r[:, None] < r

    return D[mask] - min_spacing

def poisson_disc_samples(N_turbs, domain, R=[250., 1000.], turb_locs=None):
    '''generates plant layout with number of turbines and domain within which 
    the turbines must be located'''

    if turb_locs is None:
        turb_locs = 0.*np.random.uniform(low=domain[:, 0], high=domain[:, 1], size=(1, 2))

    active_indices = [i for i in range(turb_locs.shape[0])]
    while active_indices and (turb_locs.shape[0] < N_turbs):
        idx = np.random.choice(active_indices)
        active_pt = turb_locs[idx]

        counter, valid_pt = 0, False
        while (counter < 50) and not valid_pt:
            rho, theta = np.random.uniform(R[0], R[1]), np.random.uniform(0, 2*np.pi)
            new_pt = np.array([[active_pt[0] + rho*np.cos(theta), active_pt[1] + rho*np.sin(theta)]])

            tf_inDomain = (domain[0, 0] <= new_pt[0, 0]) and (new_pt[0, 0] <= domain[0, 1]) and \
                          (domain[1, 0] <= new_pt[0, 1]) and (new_pt[0, 1] <= domain[1, 1])
            if not tf_inDomain:
                counter += 1
                continue

            D = np.sqrt(np.sum((turb_locs - new_pt)**2, axis=1))
            tf_farFromOthers = np.all(R[0] <= D)
            if not tf_farFromOthers:
                counter += 1
                continue

            valid_pt = True

        if valid_pt:
            turb_locs = np.concatenate((turb_locs, new_pt), axis=0)

            active_indices.append(turb_locs.shape[0]-1)
        else:
            active_indices.remove(idx)

    return turb_locs
