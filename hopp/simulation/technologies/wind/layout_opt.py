# Implements WPGNN model for HOPP
# Adapted from example_opt and wpgnn_demo
# https://github.com/NREL/WPGNN

import csv
import numpy as np
import yaml
import matplotlib.pyplot as plt

from hopp.simulation.base import BaseClass
from hopp.simulation.technologies.sites import SiteInfo
from hopp.type_dec import resource_file_converter

from wpgnn.wpgnn import WPGNN
from wpgnn.playgen import PLayGen
from wpgnn import utils

from graph_nets.utils_tf import *
from graph_nets.utils_np import graphs_tuple_to_data_dicts

from floris.tools import FlorisInterface

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
tf.get_logger().setLevel('ERROR')
from scipy import optimize
import tensorflow as tf

def layout_opt(site, config, plot=False, verbose=False) -> (np.array, np.array):
    '''Runs a layout optimization using WPGNN to calculate turbine powers
    param:
        config : dict 
        model_path : str
            contains path to trained WPGNN model
        plot : bool = False
            plot before and after plant layouts
        verbose : bool = False
            display all output information relevant to the optimization
    
    returns:
        x : np.array
            starting turbine coordinates (input to the optimization)
        x_opt : np.array
            optimized turbine locations

    TODO
        * make plant specs configurable by yaml file/config dict, rather than hard coding
        * train WPGNN models to account for different hub heights/turbine wattages? Or 
        is it valid to assume the optimal layout doesn't depend on those factors?
        * finish integrating into HOPP (no errors)
        * support boundary drawn by verticies provided in site
        * would it be better to have a separate "Optimization" class, like there is for
        wind_plant and pv_plant? So this would be extendable to optimizing more than just wind?
    '''

    # initialize WPGNN model (note that trained model uses default args)
    model = WPGNN(model_path=config.layout_opt['wpgnn_model'])

    # set site paramters
    # TODO use config dict to set these parameters instead of hard coding
    domain = np.array(
        [[-1000., 1000.],
            [-1000., 1000.]]
    )
    num_turbines = 12
    x = poisson_disc_samples(num_turbines, domain, R=[250., 350.])
    

    # extract resource data
    wind_resource_data = site.wind_resource.data
    num_simulations = len(wind_resource_data['data'])
    ws, wd = parse_resource_data(site)
    yaw = np.zeros((num_turbines, 1))
    ti = 0.08 # turbulence intensity TODO does it matter which value to put for this?

    ''' 
    NOTE
    * WPGNN is trained on turbines w/ the following specs
        - 3.4 MW rated power
        - 130 m rotor diameter
        - 110 m hub height
      currently this cannot be configured
    *
    
    
    '''
    if plot: 
        plt.figure(figsize=(4, 4))
        plt.scatter(x[:, 0], x[:, 1], s=15, facecolor='b', edgecolor='k')
        xlim = plt.gca().get_xlim()
        ylim = plt.gca().get_ylim()
        plt.xlim(np.minimum(xlim[0], ylim[0]), np.maximum(xlim[1], ylim[1]))
        plt.ylim(np.minimum(xlim[0], ylim[0]), np.maximum(xlim[1], ylim[1]))
        plt.gca().set_aspect(1.)
        plt.title('Number of Turbines: {}'.format(x.shape[0]))

    x_opt, _ = perform_optimization(model, x, ws, wd, ti, domain, num_simulations, verbose)
    
    if plot:
        plt.figure(figsize=(4, 4))
        plt.scatter(x_opt[:, 0], x_opt[:, 1], s=15, facecolor='b', edgecolor='k')
        xlim = plt.gca().get_xlim()
        ylim = plt.gca().get_ylim()
        plt.xlim(np.minimum(xlim[0], ylim[0]), np.maximum(xlim[1], ylim[1]))
        plt.ylim(np.minimum(xlim[0], ylim[0]), np.maximum(xlim[1], ylim[1]))
        plt.gca().set_aspect(1.)
        plt.title('Number of Turbines: {}'.format(x_opt.shape[0]))
        plt.show()

    return x, x_opt

def perform_optimization(model, x, ws, wd, ti, domain, num_simulations, verbose):
    
    N_turbs = x.shape[0]
    yaw = np.zeros((N_turbs, wd.size))

    # Set constraints
    # 1) minimum turbine space > 250 m
    # 2) box domain constaints
    # 3) yaw angles remain at zero throughout the optimization
    spacing_constraint = {'type': 'ineq', 'fun': spacing_func, 'args': [0, 250.]}

    A = np.eye(N_turbs*2)
    lb = np.repeat(np.expand_dims(domain[:, 0], axis=0), N_turbs, axis=0).reshape((-1, ))
    ub = np.repeat(np.expand_dims(domain[:, 1], axis=0), N_turbs, axis=0).reshape((-1, ))
    domain_constraint = optimize.LinearConstraint(A, lb, ub)

    constraints = [spacing_constraint, domain_constraint]

    res = optimize.minimize(objective, x.reshape((-1, )),
                            args=(yaw, ws, wd, ti, model, num_simulations, verbose),
                            method='SLSQP', jac=True,
                            constraints=constraints, 
                            options={'disp': verbose, 'maxiter': 20})

    x = res.x.reshape((-1, 2))

    return x, yaw

def objective(x, yaw, ws, wd, ti, model, num_simulations, verbose):
    x = x.reshape((-1, 2))
    num_turbines = x.shape[0]

    x_dict_list = build_dict(x, yaw, ws, wd, ti, model, num_simulations)
    x_graph_tuple = data_dicts_to_graphs_tuple(x_dict_list)
    x_graph_tuple = x_graph_tuple.replace(nodes=tf.Variable(x_graph_tuple.nodes))

    AEP, dAEP = eval_model(x_graph_tuple, model)

    dAEP = dAEP.numpy()/np.array([[75000., 85000., 15.]]) # unnorm x.nodes
    dAEP = dAEP[:, :2] # remove third row, yaw isn't used in this optimization
    dAEP = np.sum(dAEP.reshape((num_simulations, num_turbines * 2)), axis=0)

    if verbose:
        print('AEP: ', float(AEP))
        print('dAEP:\n', dAEP)
        print('x:\n', x)
        print()

    return AEP.numpy(), dAEP

@tf.function
def eval_model(x, model):
    with tf.GradientTape() as tape:
        tape.watch(x.nodes)

        # TODO
        plant_power = 5e8 * model(x).globals[:, 0] / 1e6 # unnorm power

        # expected power, not cumulative energy
        AEP = -1. * tf.reduce_sum(plant_power) # / (1e2 * 3600) ### 3600 s = 1 hr; negative to convert max to min; convert to MWh

    dAEP = tape.jacobian(AEP, x.nodes) # dAEP.shape = (num_turbines * 8760, 3)
    '''
    hour 1:
    x1, y1, yaw1;
    ...
    xn, yn, yawn;

    hour 2:
    x1, y, yaw1,;
    ...
    xn, yn, yawn
    
    REMOVE YAW + RESHAPE:
    x1, y1, ..., xn, yn; # hour 1
    x1, y1, ..., xn, yn; # hour 2
    
    SUM ALONG AXIS 1
    x1, y1, ..., xn, yn # final gradient, shape  = (num_turbines * 2, )
    '''

    return AEP, dAEP

def build_dict(x, yaw, ws, wd, ti, model, num_simulations, normalize=True):
    # Construct data format for WPGNN
    x_dict_list = []

    for i in range(num_simulations):
        uv = utils.speed_to_velocity([ws[i], wd[i]])
        edges, senders, receivers = utils.identify_edges(x[:, :2], wd[i], cone_deg=15)
        x_dict_list.append({'globals': np.array([uv[0], uv[1], ti]),
                            'nodes': np.concatenate((x, yaw[:, i].reshape((-1, 1))), axis=1),
                            'edges': edges,
                            'senders': senders,
                            'receivers': receivers})       

    if normalize:
        x_dict_list, _ = utils.norm_data(xx=x_dict_list, scale_factors=model.scale_factors)

    return x_dict_list

def spacing_func(x, n_windDirs=0, min_spacing=250.):
    x = x.reshape((-1, 2+n_windDirs))[:, :2]

    D = np.sqrt(np.sum((np.expand_dims(x, axis=0) - np.expand_dims(x, axis=1))**2, axis=2))

    r = np.arange(D.shape[0])
    mask = r[:, None] < r

    return D[mask] - min_spacing

def poisson_disc_samples(N_turbs, domain, R=[250., 1000.], turb_locs=None):
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

def parse_resource_data(site):

    # extract data for simulation
    speeds = np.zeros(len(site.wind_resource.data['data']))
    wind_dirs = np.zeros(len(site.wind_resource.data['data']))
    data_rows_total = 4
    if np.shape(site.wind_resource.data['data'])[1] > data_rows_total:
        height_entries = int(np.round(np.shape(site.wind_resource.data['data'])[1]/data_rows_total))
        data_entries = np.empty((height_entries))
        for j in range(height_entries):
            data_entries[j] = int(j*data_rows_total)
        data_entries = data_entries.astype(int)
        for i in range((len(site.wind_resource.data['data']))):
            data_array = np.array(site.wind_resource.data['data'][i])
            speeds[i] = np.mean(data_array[2+data_entries])
            wind_dirs[i] = np.mean(data_array[3+data_entries])
    else:
        for i in range((len(site.wind_resource.data['data']))):
            speeds[i] = site.wind_resource.data['data'][i][2]
            wind_dirs[i] = site.wind_resource.data['data'][i][3]

    return speeds, wind_dirs

