
# NOTE adapted from WPGNN optimization example

import os
# import WPGNN.utils  
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import numpy as np
import tensorflow as tf
tf.get_logger().setLevel('ERROR')
from wpgnn_integration.WPGNN.wpgnn import WPGNN
from scipy import optimize
from graph_nets.utils_tf import *
from graph_nets.utils_np import graphs_tuple_to_data_dicts
 


# Set site details
N_turbs = 12
domain = np.array([[-1000., 1000.],
                    [-1000., 1000.]])
x = poisson_disc_samples(N_turbs, domain, R=[250., 350.])

wind_rose = np.load('wind_rose.npy')
ws, wd, ti = np.arange(0., 20., 1.), np.arange(0., 360., 5.), 0.06

# Set WPGNN parameters and intialize model
load_model_path = 'model/wpgnn.h5'
scale_factors = {'x_globals': np.array([[0., 25.], [0., 25.], [0.09, 0.03]]),
                    'x_nodes': np.array([[0., 75000.], [0., 85000.], [15., 15.]]),
                    'x_edges': np.array([[-100000., 100000.], [0., 75000.]]),
                  'f_globals': np.array([[0., 500000000.], [0., 100000.]]),
                    'f_nodes': np.array([[0., 5000000.], [0.,25.]]),
                    'f_edges': np.array([[0., 0.]])}
N_edge_features, N_node_features, N_global_features = 2, 3, 3

graph_size = []
graph_size += [[32, 32, 32] for _ in range(1)]
graph_size += [[16, 16, 16] for _ in range(2)]
graph_size += [[ 8,  8,  8] for _ in range(2)]
graph_size += [[ 4,  2,  2]]

model = WPGNN(N_edge_features, N_node_features, N_global_features, graph_size,
                  scale_factors=scale_factors,
                  model_path=load_model_path)

model.print_weights()

# returns turbine locations
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