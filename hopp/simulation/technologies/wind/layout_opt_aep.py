from attrs import define

from hopp.simulation.technologies.wind.layout_opt_interface import LayoutOptInterface
from graph_nets.utils_tf import *
from graph_nets.utils_np import graphs_tuple_to_data_dicts

import numpy as np
import tensorflow as tf


@define
class LayoutOptAEP(LayoutOptInterface):
    def objective(self, x, verbose) -> (np.array, np.array): 
        x_in = x.reshape((-1, 2))

        x_dict_list = self.build_dict(x_in)
        x_graph_tuple = data_dicts_to_graphs_tuple(x_dict_list)
        x_graph_tuple = x_graph_tuple.replace(nodes=tf.Variable(x_graph_tuple.nodes))

        AEP, dAEP = self._eval_model(self.model, x_graph_tuple)

        dAEP = dAEP/np.array([[75000., 85000., 15.]]) # unnorm x.nodes
        dAEP = dAEP[:, :2] # remove third row, yaw isn't used in this optimization
        dAEP = np.sum(dAEP.reshape((self.num_simulations, self.plant_config.num_turbines * 2)), axis=0)

        if verbose:
            print(f'FUNCTION EVAULATION {self._opt_counter}')
            print('AEP: ', float(AEP))
            print('dAEP:\n', dAEP)
            print('x:\n', x_in)
            print()
            self._opt_counter += 1

        return AEP, dAEP
    
    # @tf.function
    def _eval_model(self, model, x):
        with tf.GradientTape() as tape:
            tape.watch(x.nodes)

            # TODO
            plant_power = 5e8 * model(x).globals[:, 0] / 1e6 # unnorm power

            # expected power, not cumulative energy
            AEP = -1. * tf.reduce_sum(plant_power) # / (1e2 * 3600) ### 3600 s = 1 hr; negative to convert max to min; convert to MWh

        dAEP = tape.jacobian(AEP, x.nodes) # dAEP.shape = (num_turbines * 8760, 3)

        return AEP.numpy(), dAEP.numpy()