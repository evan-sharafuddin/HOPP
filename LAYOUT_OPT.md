# Layout Optimization using WPGNN
This branch includes a layout optimizer using WPGNN that is partially integrated into HOPP. 
## Relevant Files
```
hopp/simulation/technologies/wind/
    layout_opt_interface.py
    layout_opt_aep.py
    layout_opt_h2_prod.py

examples/
    inputs/layout_opt/
        example_opt_aep.yaml
        example_opt_h2_prod.yaml
    08-example_opt_aep.py
    09-example_opt_h2_prod.py
    10-layout_opt_comparison.ipynb
``` 

Existing files that were altered/used include
```
hopp/simulation/technologies/wind/
    wind_plant.py
    floris.py

examples/inputs/floris/
    gch.yaml
    nrel_5MW.yaml

```

## Getting Started
* Make sure you have a working conda environment for HOPP
* Activate your environment, then run the following commands:
```
pip install wpgnn-1.0.0.tar.gz
conda install -c anaconda h5py
conda install -c conda-forge tensorflow=2.7.0
```
* Select the objective for layout optimization (currently only AEP and H2 Production are supported)
* navigate to the relevant `.yaml` file and configure the plant to your liking
    * **NOTE THE FOLLOWING**
        * Currently, only square layouts are supported. The default layout is 1000m x 1000m, and is set inside ```hopp/simulation/technologies/wind/layout_opt_interface```.
        * The turbine locations and number of turbines will overwrite the FLORIS config file.
        * The turbine diameter from the FLORIS config is used in the optimization -- there is no turbine diameter to configure in the layout opt config 
        * If running the code in a Jupyter notebook vs an ordinary python script, make sure to comment/uncomment the cooresponding file paths for WPGNN and floris config 
* Run one of the three provided example scripts/notebooks (08-10). A `HoppInterface` is created using one of the layout optimization configurations, which automatically calls the optimizer and instantiates FLORIS with the optimized turbine layouts.
    * 08: optimize the plant layout based on AEP
    * 09: optimize the plant layout based on H2 Production
    * 10: compare the results of the above two cost functions
        * Since the H2 production cost function is essentially a scaled version of the AEP cost function, results are nearly, if not completely, identical

## Development & Code Details
### `LayoutOptInterface`
* An interface was created for easy addition of different cost function. Each cost function should inheret from this interface, which holds functions to define initial layout, run the optimizer, define constraints, etc
* A factory class, `LayoutOptFactory`, handles defining the correct instance of the optimizer based on the input to the yaml. Make sure to add the name of the cost function to this factory whenever you are creating new cost functions.
* A conversion factor (cf) was added to account for different turbine sizes. WPGNN was trained on a turbine with diameter 130m, so to account for smaller/larger turbines, the geometry of the system (i.e., domain and spacing constraints) are multiplied by this conversion factor. This does not account for differences in turbine power generation, etc but should still give a reasonible approximation for the optimial layout of a plant with given turbine diameter.
* SciPy's SLSQP solver supports inequality constraints, which are currently used to implement boundary/domain and spacing constraints. A "hole" constraint was also added, which allows for the user to add a rectangular region centered about the origin in which turbines cannot be placed.
    * NOTE: the hole constraint is not completely finished... it seems like the inequalities are carving out a "plus" shape rather than the square/rectangle as the exclusion zone for the turbines. 
    * The hole constraint is commented out by default in `layout_opt_interface.py`
* Although a specific interface is not defined for adding constraints, the user is referred to line ~300 of `layout_opt_interface.py`, where the hole constraint is defined and added to the list of constraints.
* There are a few aspects of the code that are still a work in progress and that need to be validated, so use caution.
    * The majority of this developemnt was focused on the results of the optimizer, and not the results of FLORIS using the optimized turbine layouts. There is a chance that the results from FLORIS will not make sense given these layouts, and testing of this is encouraged

*To gain more insight on how the optimization is implemented, and how to make changes to the current framework, the user is encouraged to look at the following files. These include many comments explaining some of the more specific steps:*
* ```layout_opt_interface.py```
* `layout_opt_aep.py`
* `layout_opt_h2_prod.py`

*To understand WPGNN and how the optimization itself works, the user is directed to the following resources:*
* https://github.com/NREL/WPGNN
* Harrison-Atlas, D., Glaws, A., King, R. N., and Lantz, E. "Geodiverse prospects for wind plant controls targeting land use and economic objectives".

## Questions? Contact:
* Evan Sharafuddin (evansharafuddin@gmail.com)

