from attrs import define, field
from typing import List

from hopp.simulation.technologies.wind.layout_opt_interface import LayoutOptInterface
from graph_nets.utils_tf import *
from graph_nets.utils_np import graphs_tuple_to_data_dicts

import numpy as np
import tensorflow as tf
import pandas as pd
import math

from hopp.simulation.technologies.hydrogen.electrolysis.PEM_H2_LT_electrolyzer_Clusters import PEM_H2_Clusters

@define
class LayoutOptH2Prod(LayoutOptInterface):
    '''Layout optimizer that maximizes hydrogen production (NOT including electrolyzer degredation)
    https://github.com/NREL/WPGNN
    Harrison-Atlas, D., Glaws, A., King, R. N., and Lantz, E. "Geodiverse prospects for wind plant controls targeting land use and economic objectives".
    
    NOTE /opt/anaconda3/envs/hopp/lib/python3.8/site-packages/scipy/optimize/_minpack_py.py:906: OptimizeWarning: Covariance of the parameters could not be estimated
    warnings.warn('Covariance of the parameters could not be estimated'
    * this warning should be ok 
    
    '''

    # NOTE all of these are defined in the PEM_H2_Clusters instance
    # P_STACK_RATING = 1000 # kW
    # N_CELLS = 130 # cells/stack
    # DT = 3600 # s
    # CELL_ACTIVE_AREA = 1920 # cm^2
    # MAX_CURRENT_DENSITY = 2 # A/cm^2
    # TURNDOWN_RATIO = 0.1 # min_power/nameplate_power [kW/kW]
    # MAX_CELL_CURRENT = CELL_ACTIVE_AREA * MAX_CURRENT_DENSITY # A
    # MIN_CELL_CURRENT = TURNDOWN_RATIO * MAX_CELL_CURRENT # TODO is this the correct interpretation?
    
    # T_C = 80 # stack temperature [C]

    clusters: PEM_H2_Clusters = field(init=False)
    cluster_size_mw: int = field(init=False)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        #These are good defaults - don't need to worry about them
        simulation_length = 8760 #1 year
        plant_life = 30 #years
        use_degradation_penalty=True
        grid_connection_scenario = 'off-grid'
        EOL_eff_drop = 10
        pem_control_type = 'basic' #basic control = baseline control
        user_params = {
            "user_defined_EOL_percent_eff_loss": True,
            "eol_eff_percent_loss": EOL_eff_drop,
            "user_defined_eff": False,
            "rated_eff_kWh_pr_kg": [],
        }

        self.cluster_size_mw = self.plant_config.turbine_rating_kw * self.plant_config.num_turbines / 1e3 # NOTE this is the turbine rating defined in example_opt_aep.yaml

        self.clusters = PEM_H2_Clusters(
            self.cluster_size_mw,
            plant_life,
            **user_params,             
        )

    def objective(self, x, verbose) -> (np.float64, np.array): 
        '''AEP objective function
        
        param:
            self: LayoutOptH2Prod
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

        AEP, dAEP = LayoutOptH2Prod._eval_model(self.model, x_graph_tuple, self.clusters)

        dAEP = dAEP.numpy()/np.array([[75000., 85000., 15.]]) # unnorm x.nodes
        dAEP = dAEP[:, :2] # remove third row, yaw isn't used in this optimization
        dAEP = np.sum(dAEP.reshape((self.num_simulations, self.plant_config.num_turbines * 2)), axis=0)

        if verbose:
            print(f'FUNCTION EVAULATION {self._opt_counter}')
            print('AEP: ', float(AEP))
            print('dAEP:\n', dAEP)
            print('x:\n', x_in)
            print()
            self._opt_counter += 1

        return AEP.numpy(), dAEP

    @staticmethod
    # @tf.function
    def _eval_model(model, x, clusters) -> (tf.Tensor, tf.Tensor):
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
        '''

        with tf.GradientTape() as tape:
            tape.watch(x.nodes)
            
            # 1
            P = 5e8 * model(x).globals[:, 0] / 1e3 # TODO assuming powers in kW
            
            # 2
            zero_mask = P < (clusters.turndown_ratio * clusters.max_stacks * 1e3)
            curtail_mask = P > clusters.max_stacks * 1e3
            
            P = tf.where(zero_mask, 0., P)
            P = tf.where(curtail_mask, tf.constant(clusters.max_stacks * 1e3, dtype=tf.float64), P)

            # 3
            n_stacks = clusters.max_stacks * 1e3 / clusters.stack_rating_kW
            P_stack = P / n_stacks

            # 4 
            get_i = lambda p, P : p[0] * P**3 + p[1] * P**2 + p[2] * P + p[3] * P**0.5 + p[4]
            i_stack = get_i(clusters.curve_coeff, P_stack)
            i_stack = tf.where(zero_mask, 0., i_stack) # ensure that zero power cooresponds to zero current

            # 5 
            n_dot_h2_stack = clusters.N_cells * i_stack / (2 * clusters.F) # mol/s
            m_dot_h2_stack = n_dot_h2_stack * (1 / clusters.moles_per_g_h2) * (clusters.dt / 1e3) # mol/s -> kg/hr
            
            # 6 
            m_dot_h2 = m_dot_h2_stack * n_stacks

            # add vector of hourly H2 production rates and multiply by 30 to get estimated lifetime hydrogen production
            m_h2 = -1. * tf.reduce_sum(m_dot_h2) # convert to minimum for SciPy compatibility

        dm_h2 = tape.jacobian(m_h2, x.nodes) # dm_h2.shape = (num_turbines * 8760, 3)

        return m_h2, dm_h2
    





    # @staticmethod
    # def _calc_current(P, p1, p2, p3, p4, p5): #calculates i-v curve coefficients given the stack power and stack temp
    #     '''
    #     Adapted from hopp.simulation.technologies.hydrogen.electrolysis.PEM_H2_LT_electrolyzer_Clusters.py
    #     '''

    #     i_stack=p1*(P**3) + p2*(P**2) + (p3*P) + (p4*P**(1/2)) + p5
    #     return i_stack 

    # def _iv_curve(self):
    #     '''
    #     Adapted from hopp.simulation.technologies.hydrogen.electrolysis.PEM_H2_LT_electrolyzer_Clusters.py
    #     -----------
    #     This is a new function that creates the I-V curve to calculate current based
    #     on input power and electrolyzer temperature

    #     current range is 0: max_cell_current+10 -> PEM have current density approx = 2 A/cm^2

    #     temperature range is 40 degC : rated_temp+5 -> temperatures for PEM are usually within 60-80degC

    #     calls cell_design() which calculates the cell voltage
    #     '''

    #     # current_range = np.arange(0,self.max_cell_current+10,10) 
    #     current_range = np.arange(self.MIN_CELL_CURRENT ,self.MAX_CELL_CURRENT+10, 10) 
    #     temp_range = np.arange(40, self.T_C+5, 5)
    #     idx = 0
    #     powers = np.zeros(len(current_range)*len(temp_range))
    #     currents = np.zeros(len(current_range)*len(temp_range))
    #     temps_C = np.zeros(len(current_range)*len(temp_range))
    #     for i in range(len(current_range)):
            
    #         for t in range(len(temp_range)):
    #             powers[idx] = current_range[i]*self.cell_design(temp_range[t],current_range[i])*self.N_CELLS*(1e-3) #stack power
    #             currents[idx] = current_range[i]
    #             temps_C[idx] = temp_range[t]
    #             idx = idx+1
    #     df=pd.DataFrame({'Power':powers,'Current':currents,'Temp':temps_C}) #added
    #     temp_oi_idx = df.index[df['Temp']==self.T_C]      #added  
    #     # curve_coeff, curve_cov = scipy.optimize.curve_fit(calc_current, (powers,temps_C), currents, p0=(1.0,1.0,1.0,1.0,1.0,1.0)) #updates IV curve coeff
    #     curve_coeff, curve_cov = scipy.optimize.curve_fit(LayoutOptH2Prod._calc_current, (df['Power'][temp_oi_idx].values,df['Temp'][temp_oi_idx].values), df['Current'][temp_oi_idx].values, p0=(1.0,1.0,1.0,1.0,1.0,1.0))
    #     return curve_coeff    
    