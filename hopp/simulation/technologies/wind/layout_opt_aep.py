from attrs import define

from hopp.simulation.technologies.wind.layout_opt_interface import LayoutOptInterface
from graph_nets.utils_tf import *
from graph_nets.utils_np import graphs_tuple_to_data_dicts

import numpy as np
import tensorflow as tf


@define
class LayoutOptAEP(LayoutOptInterface):
    '''Layout optimizer that maximizes AEP (expected energy generation)
    https://github.com/NREL/WPGNN
    Harrison-Atlas, D., Glaws, A., King, R. N., and Lantz, E. "Geodiverse prospects for wind plant controls targeting land use and economic objectives".
    '''

    def objective(self, x, verbose) -> (np.float64, np.array): 
        '''AEP objective function
        
        param:
            self: LayoutOptAEP
            x: np.array
                current plant layout to be evaluated
            verbose: bool 
                from LayoutOptInterface.opt()
        
        returns:
            AEP: np.float64
                AEP value from the current plant layout
            dAEP: np.array
                gradient used in optimization, shape = (num_turbines * 2, )

                [dAEP/dx1, dAEP/dy1, ..., dAEP/dxn, dAEP/dyn]
        '''

        x_in = x.reshape((-1, 2))

        x_dict_list = self.build_dict(x_in)
        x_graph_tuple = data_dicts_to_graphs_tuple(x_dict_list)
        x_graph_tuple = x_graph_tuple.replace(nodes=tf.Variable(x_graph_tuple.nodes))

        AEP, dAEP = LayoutOptAEP._eval_model(self.model, x_graph_tuple)

        dAEP = dAEP.numpy()/np.array([[75000., 85000., 15.]]) # unnorm x.nodes
        dAEP = dAEP[:, :2] # remove third row, yaw isn't used in this optimization
        dAEP = np.sum(dAEP.reshape((self.num_simulations, self.plant_config.num_turbines * 2)), axis=0)

        print(f'FUNCTION EVAULATION {self._opt_counter}')
        if verbose:
            print('AEP: ', float(AEP))
            print('dAEP:\n', dAEP)
            print('x:\n', x_in)
            print()
        
        self._opt_counter += 1

        return AEP.numpy(), dAEP
    
    @staticmethod
    @tf.function(experimental_relax_shapes=True)
    def _eval_model(model, x) -> (tf.Tensor, tf.Tensor):
        '''function used for WPGNN model evaluation step
        
        @tf.function decorator used for increased performance

        param:
            model: WPGNN
                trained WPGNN model
            x: np.array
                current plant layout
        
        returns:
            AEP: tf.Tensor
                AEP from the current plant layout
            dAEP: tf.Tensor
                jacobian calculated using tensorflow's GradientTape, shape=(num_simulations * num_turbines, 3)
                
                [ # first timestep
                 [dAEP/dx1, dAEP/dy1, dAEP/dyaw_1],
                  ... 
                 [dAEP/dxn, dAEP/dyn, dAEP/dyaw_n],
                  # second timestep
                 [dAEP/dx1, dAEP/dy1, dAEP/dyaw_1],
                  ... 
                 [dAEP/dxn, dAEP/dyn, dAEP/dyaw_n],
                  ...
                  ...
                  # final timestep
                 [dAEP/dx1, dAEP/dy1, dAEP/dyaw_1],
                  ... 
                 [dAEP/dxn, dAEP/dyn, dAEP/dyaw_n],
                ]

        NOTE error message which prompted experimental_relax_shapes=True option
            WARNING:tensorflow:6 out of the last 6 calls to <function pfor.<locals>.f at 0x7f8c4212e280> 
            triggered tf.function retracing. Tracing is expensive and the excessive number of tracings could 
            be due to (1) creating @tf.function repeatedly in a loop, (2) passing tensors with different shapes,
            (3) passing Python objects instead of tensors. For (1), please define your @tf.function outside of 
            the loop. For (2), @tf.function has experimental_relax_shapes=True option that relaxes argument
            shapes that can avoid unnecessary retracing. For (3), please refer to
            https://www.tensorflow.org/guide/function#controlling_retracing and 
            https://www.tensorflow.org/api_docs/python/tf/function for  more details.
        This originated after commit 75c956ee30e1d393946890724871dfcce4fbe437 "layout opt with AEP objective now 
        integrated with HOPP (floris solver). Needs testing", not sure why... no major changes were made to the code

        '''

        with tf.GradientTape() as tape:
            tape.watch(x.nodes)

            plant_power = 5e8 * model(x).globals[:, 0] / 1e5 # unnorm power, divide by 1e6 to "normalize" Jacobian for optimization

            AEP = -1. * tf.reduce_sum(plant_power) # AEP using time series instead of wind rose

        dAEP = tape.jacobian(AEP, x.nodes) # dAEP.shape = (num_turbines * 8760, 3)

        return AEP, dAEP