from hopp.simulation.technologies.wind.wpgnn_for_hopp import WPGNNForHOPP
from wpgnn.wpgnn import WPGNN

# import os
# os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
# import numpy as np
# import tensorflow as tf
# tf.get_logger().setLevel('ERROR')
# from wpgnn import WPGNN
# from scipy import optimize
# import tensorflow as tf
# from graph_nets.utils_tf import *
# from graph_nets.utils_np import graphs_tuple_to_data_dicts
# import utils

# import matplotlib.pyplot as plt


def layout_opt(site, config, model_path):
    wpgnn = WPGNNForHOPP(site, config, model_path)


    def main():
        # Set site details
        N_turbs = config.num_turbines
        domain = np.array([[-1000., 1000.],
                        [-1000., 1000.]]) # in m, hardcoded for now (TODO transition to using site verts in yaml?)
        x = poisson_disc_samples(N_turbs, domain, R=[250., 350.])

        plt.figure(figsize=(4, 4))
        plt.scatter(x[:, 0], x[:, 1], s=15, facecolor='b', edgecolor='k')
        xlim = plt.gca().get_xlim()
        ylim = plt.gca().get_ylim()
        plt.xlim(np.minimum(xlim[0], ylim[0]), np.maximum(xlim[1], ylim[1]))
        plt.ylim(np.minimum(xlim[0], ylim[0]), np.maximum(xlim[1], ylim[1]))
        plt.gca().set_aspect(1.)
        plt.title('Number of Turbines: {}'.format(x.shape[0]))
        
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

        x_baseline, yaw_baseline = perform_optimization(model, x, ws, wd, ti, wind_rose, domain, include_yaw=False)
        
        # x_steering, yaw_steering = perform_optimization(model, x, ws, wd, ti, wind_rose, domain, include_yaw=True)

        plt.figure(figsize=(4, 4))
        plt.scatter(x_baseline[:, 0], x_baseline[:, 1], s=15, facecolor='b', edgecolor='k')
        xlim = plt.gca().get_xlim()
        ylim = plt.gca().get_ylim()
        plt.xlim(np.minimum(xlim[0], ylim[0]), np.maximum(xlim[1], ylim[1]))
        plt.ylim(np.minimum(xlim[0], ylim[0]), np.maximum(xlim[1], ylim[1]))
        plt.gca().set_aspect(1.)
        plt.title('Number of Turbines: {}'.format(x_baseline.shape[0]))
        plt.show()
        
        print('done')

    def perform_optimization(model, x, ws, wd, ti, wind_rose, domain, include_yaw=False):
        
        N_turbs = x.shape[0]
        yaw = np.zeros((N_turbs, wd.size))

        A = np.eye(N_turbs*2)
        lb = np.repeat(np.expand_dims(domain[:, 0], axis=0), N_turbs, axis=0).reshape((-1, ))
        ub = np.repeat(np.expand_dims(domain[:, 1], axis=0), N_turbs, axis=0).reshape((-1, ))
        domainConstraint = optimize.LinearConstraint(A, lb, ub)

        # Set constraints
        # 1) minimum turbine space > 250 m
        # 2) box domain constaints
        # 3) (if applicable) yaw angles between 0-30 deg.
        if include_yaw:
            spacing_constraint = {'type': 'ineq', 'fun': spacing_func, 'args': [wd.size, 250.]}

            A = np.eye(x.size+yaw.size)
            lb = np.array([list(domain[:, 0])+[0. for _ in range(wd.size)]])
            lb = np.repeat(lb, N_turbs, axis=0).reshape((-1, ))
            ub = np.array([list(domain[:, 1])+[30. for _ in range(wd.size)]])
            ub = np.repeat(ub, N_turbs, axis=0).reshape((-1, ))
            domain_and_yaw_constraint = optimize.LinearConstraint(A, lb, ub)

            constraints = [spacing_constraint, domain_and_yaw_constraint]
        else:
            spacing_constraint = {'type': 'ineq', 'fun': spacing_func, 'args': [0, 250.]}

            A = np.eye(N_turbs*2)
            lb = np.repeat(np.expand_dims(domain[:, 0], axis=0), N_turbs, axis=0).reshape((-1, ))
            ub = np.repeat(np.expand_dims(domain[:, 1], axis=0), N_turbs, axis=0).reshape((-1, ))
            domain_constraint = optimize.LinearConstraint(A, lb, ub)

            constraints = [spacing_constraint, domain_constraint]

        if include_yaw:
            x_yaw = np.concatenate((x, yaw), axis=1)

            res = optimize.minimize(objective_wYaw, x_yaw.reshape((-1, )),
                                    args=(ws, wd, ti, wind_rose, model),
                                    method='SLSQP', jac=True,
                                    constraints=constraints)

            x_yaw = res.x.reshape((N_turbs, 2+wd.size))
            x, yaw = x_yaw[:, :2], x_yaw[:, 2:]

        else:
            res = optimize.minimize(objective_noYaw, x.reshape((-1, )),
                                    args=(yaw, ws, wd, ti, wind_rose, model),
                                    method='SLSQP', jac=True,
                                    constraints=constraints)

            x = res.x.reshape((-1, 2))

        return x, yaw

    def objective_wYaw(x_yaw, ws, wd, ti, wind_rose, model):
        x_yaw = x_yaw.reshape((-1, 2+wd.size))
        x, yaw = x_yaw[:, :2], x_yaw[:, 2:]
        n_turbines = x.shape[0]

        wind_rose = tf.convert_to_tensor(wind_rose, dtype=np.float64)

        x_dict_list = build_dict(x, yaw, ws, wd, ti, model)
        x_graph_tuple = data_dicts_to_graphs_tuple(x_dict_list)
        x_graph_tuple = x_graph_tuple.replace(nodes=tf.Variable(x_graph_tuple.nodes))

        AEP, dAEP = eval_model(x_graph_tuple, wind_rose, model)

        dAEP = dAEP.numpy()/np.array([[75000., 85000., 15.]])
        dAEP = np.transpose(np.sum(dAEP.reshape((wd.size, ws.size, x.shape[0], 3)), axis=1), axes=(1, 0, 2))
        dAEP_dx, dAEP_dyaw = np.sum(dAEP[:, :, :2], axis=1), dAEP[:, :, 2]
        dAEP = np.concatenate((dAEP_dx, dAEP_dyaw), axis=1).reshape((-1, ))

        return AEP.numpy(), dAEP

    def objective_noYaw(x, yaw, ws, wd, ti, wind_rose, model):
        x = x.reshape((-1, 2))
        n_turbines = x.shape[0]

        wind_rose = tf.convert_to_tensor(wind_rose, dtype=np.float64)

        x_dict_list = build_dict(x, yaw, ws, wd, ti, model)
        x_graph_tuple = data_dicts_to_graphs_tuple(x_dict_list)
        x_graph_tuple = x_graph_tuple.replace(nodes=tf.Variable(x_graph_tuple.nodes))

        AEP, dAEP = eval_model(x_graph_tuple, wind_rose, model)

        dAEP = dAEP.numpy()/np.array([[75000., 85000., 15.]])
        dAEP = np.sum(dAEP.reshape((wd.size, ws.size, x.shape[0], 3)), axis=(0, 1))[:, :2].reshape((-1, ))

        return AEP.numpy(), dAEP

    @tf.function
    def eval_model(x, wind_rose, model):
        with tf.GradientTape() as tape:
            tape.watch(x.nodes)

            P = (500000000./1000000.)*model(x).globals[:, 0] # wind plant capacities divided by 1e6 conversion factor
            P = tf.transpose(tf.reshape(P, tf.transpose(wind_rose).shape))

            AEP = -8760.*tf.reduce_sum(P*wind_rose)

        dAEP = tape.jacobian(AEP, x.nodes)

        return AEP, dAEP

    def build_dict(x, yaw, ws, wd, ti, model, normalize=True):
        # Construct data format for WPGNN
        x_dict_list = []
        for i, wd_i in enumerate(wd):
            for j, ws_j in enumerate(ws):
                uv = utils.speed_to_velocity([ws_j, wd_i])
                edges, senders, receivers = utils.identify_edges(x[:, :2], wd_i, cone_deg=15)
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


    if __name__ == '__main__':
        main()
