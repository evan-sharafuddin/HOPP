from typing import Optional, TYPE_CHECKING
from attrs import define, field
from abc import ABC, abstractmethod

# from hopp.utilities.log import hybrid_logger as logger

if TYPE_CHECKING:
    from hopp.simulation.technologies.wind.wind_plant import WindConfig

from hopp.simulation.technologies.sites import SiteInfo

import numpy as np
from wpgnn.wpgnn import WPGNN
from wpgnn import utils
import matplotlib.pyplot as plt
from scipy import optimize
import tensorflow as tf


@define
class LayoutOptInterface(ABC): 
    '''Interface for layout optimizations, implement this class with different objectives
    https://github.com/NREL/WPGNN
    Harrison-Atlas, D., Glaws, A., King, R. N., and Lantz, E. "Geodiverse prospects for wind plant controls targeting land use and economic objectives".
    
    param:
        site: SiteInfo
        plant_config: WindConfig
        ti: int

        model: trained WPGNN model used to calculate plant power
        x: starting plant layout for the optimization
        num_simulations: length of simulation / time step (usually 8760)
        ws: wind speed data time series
        wd: wind direction data time series
        yaw: yaw angles for each turbine (TODO currently these are always set to zero)
        domain: region within which turbine locations are constrained (TODO support non-square domains and use SiteInfo vertices)
        _opt_counter: used to display number of function evaluations completed

        plot : bool = False
            plot before and after plant layouts
        verbose : bool = False
            display all output information relevant to the optimization


    TODO
        * make plant specs configurable by yaml file/config dict, rather than hard coding
        * train WPGNN models to account for different hub heights/turbine wattages? Or 
        is it valid to assume the optimal layout doesn't depend on those factors?
        * support boundary drawn by verticies provided in site
        * would it be better to have a separate "Optimization" class, like there is for
        wind_plant and pv_plant? So this would be extendable to optimizing more than just wind?
        * have different trained WPGNN models for different sized turbinies (only support 3.4 MW turbine currently)
    '''

    site: SiteInfo
    plant_config: "WindConfig"
    ti: Optional[int] = field(default=0.06)

    model: WPGNN = field(init=False)
    x: np.array = field(init=False)
    num_simulations: int = field(init=False)
    ws: np.array = field(init=False)
    wd: np.array = field(init=False)
    yaw: np.array = field(init=False)
    domain: np.array = field(init=False)
    _opt_counter: int = field(init=False)

    def __attrs_post_init__(self):
        '''Initialize the remaining variables'''

        self.model = WPGNN(model_path=self.plant_config.wpgnn_model)

        # TODO use config dict to set these parameters instead of hard coding
        self.domain = np.array([[-1000., 1000.],
                           [-1000., 1000.]])
        
        self.x = self.poisson_disc_samples(R=[250., 350.])

        self.num_simulations = len(self.site.wind_resource.data['data'])

        self.ws, self.wd = self.parse_resource_data()
        self.yaw = np.zeros((self.plant_config.num_turbines, self.wd.size))

        self._opt_counter = 1


    def poisson_disc_samples(self, R=[250., 1000.]) -> np.array:
        '''Generate random scatter layout
        param:
            self: LayoutOptInterface
            R: list
                [min, max] distance between turbines

        returns:
            turb_locs: np.array
        '''

        N_turbs = self.plant_config.num_turbines
        domain = self.domain
        
        if self.plant_config.turbine_locations is None:
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
        

    def parse_resource_data(self) -> (np.array, np.array):
        '''Parses resource data (taken from ./floris.py)'''

        site = self.site

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
    

    def build_dict(self, x) -> list:
        '''Construct input data for WPGNN model evaluation
        
        param: 
            self: LayoutOptInterface
            x: np.array
                Current turbine locations to be evaluated
            
        returns:
            x_dict_list: list
                formatted input data
        '''

        x_dict_list = []

        for i in range(self.num_simulations):
            uv = utils.speed_to_velocity([self.ws[i], self.wd[i]])
            edges, senders, receivers = utils.identify_edges(x[:, :2], self.wd[i], cone_deg=15)
            x_dict_list.append({'globals': np.array([uv[0], uv[1], self.ti]),
                                'nodes': np.concatenate((x, self.yaw[:, i].reshape((-1, 1))), axis=1),
                                'edges': edges,
                                'senders': senders,
                                'receivers': receivers})       

        x_dict_list, _ = utils.norm_data(xx=x_dict_list, scale_factors=self.model.scale_factors)

        return x_dict_list
    

    @staticmethod
    def spacing_func(x, n_windDirs=0, min_spacing=250.) -> np.array:
        '''Function used to define nonlinear spacing constraint
        
        param:
            x: np.array
                current turbine locations
            n_windDirs: int
                number of wind direction bins (default=0 when yaw optimization is not used)
            min_spacing: float
                minimum spacing between turbines that is enforced

        returns:
            np.array
                values used in nonlinear inequality constraint
        '''
        x = x.reshape((-1, 2+n_windDirs))[:, :2]

        D = np.sqrt(np.sum((np.expand_dims(x, axis=0) - np.expand_dims(x, axis=1))**2, axis=2))

        r = np.arange(D.shape[0])
        mask = r[:, None] < r

        return D[mask] - min_spacing
    

    @staticmethod 
    def plot_layout(x):
        '''Plots np.array of turbine layouts (NOTE must call plt.show() outside of function)'''

        plt.figure(figsize=(4, 4))
        plt.scatter(x[:, 0], x[:, 1], s=15, facecolor='b', edgecolor='k')
        xlim = plt.gca().get_xlim()
        ylim = plt.gca().get_ylim()
        plt.xlim(np.minimum(xlim[0], ylim[0]), np.maximum(xlim[1], ylim[1]))
        plt.ylim(np.minimum(xlim[0], ylim[0]), np.maximum(xlim[1], ylim[1]))
        plt.gca().set_aspect(1.)
        plt.title('Number of Turbines: {}'.format(x.shape[0]))
    

    def opt(self, plot=False, verbose=False, maxiter=50) -> list:
        '''Prepares constraints and calls optimizer
        
        param:
            self: LayoutOptInterface
            plot: bool
                if True, plots showing layout before and after will be shown
            verbose: bool
                if True, information showing current AEP, dAEP, x, as well as scipy output will be displayed to terminal
            maxiter: int
                maximum number of iterations before optimizer terminates


        returns:
            x_opt: list
                optimized turbine locations
        '''

        if plot: 
            LayoutOptInterface.plot_layout(self.x)

        # Set constraints
        # 1) minimum turbine space > 250 m
        # 2) box domain constaints
        # 3) yaw angles remain at zero throughout the optimization
        spacing_constraint = {'type': 'ineq', 'fun': LayoutOptInterface.spacing_func, 'args': [0, 250.]}

        A = np.eye(self.plant_config.num_turbines*2)
        lb = np.repeat(np.expand_dims(self.domain[:, 0], axis=0), self.plant_config.num_turbines, axis=0).reshape((-1, ))
        ub = np.repeat(np.expand_dims(self.domain[:, 1], axis=0), self.plant_config.num_turbines, axis=0).reshape((-1, ))
        domain_constraint = optimize.LinearConstraint(A, lb, ub)

        constraints = [spacing_constraint, domain_constraint]

        res = optimize.minimize(self.objective, self.x.reshape((-1, )),
                                args=(verbose),
                                method='SLSQP', jac=True,
                                constraints=constraints, 
                                options={'disp': verbose, 'maxiter': maxiter})

        x_opt = res.x.reshape((-1, 2))


        if plot:
            LayoutOptInterface.plot_layout(x_opt)
            plt.show()

        return x_opt.tolist()
 

    @abstractmethod
    def objective(self, x, verbose) -> (np.float64, np.array):
        '''Optimization objective function'''
        pass


    @staticmethod
    @abstractmethod
    def _eval_model(model, x) -> (tf.Tensor, tf.Tensor):
        '''Optimization model evaluation (should be called inside objective())'''
        pass

from hopp.simulation.technologies.wind.layout_opt_aep import LayoutOptAEP
from hopp.simulation.technologies.wind.layout_opt_h2_prod import LayoutOptH2Prod

@define
class LayoutOptFactory: 
    '''Factory class to create the appropriate layout optimizer based on input yaml
    
    To add new objective, create class inheriting from the above interface and add
    key-value pair to `SUPPORTED_OBJECTIVES` static member variable below
    '''

    SUPPORTED_OBJECTIVES = {'aep': LayoutOptAEP,
                            'h2_prod': LayoutOptH2Prod,}

    def create_optimizer(site: SiteInfo, wind_config: "WindConfig"):
        objective = wind_config.layout_opt

        if type(objective) is not str:
            raise ValueError(f"Objective in configuration yaml must be of type <str>. Instead got type {type(objective)}")

        for o, c in LayoutOptFactory.SUPPORTED_OBJECTIVES.items():
            if objective == o:
                return c(site, wind_config)
        
        raise NotImplementedError(f"The objective {objective} is not currently implemented. Perhaps you made a typo?")


 