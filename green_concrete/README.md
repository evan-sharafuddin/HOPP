This file provides some info on the feature/green_cement_concrete branch of HOPP

*Notes*
* the green-steel-specific files should be unchanged
* the only changes present are in the following folders/files
    * **`HOPP/green_concrete`**: contains all data from the CEMCAP report that was used to generate this model, including CAPEX, OPEX, etc. Contains the CementPlant class and all output files (in the `outputs` directory)
    * **`green_industry_define_scenarios.py`**: somewhat similar to `green_steel_ammonia_define_scenarios.py`, but changes were made to ease modelling different cement plants. This is the file that you will run to execute a model. Configurations for the run can be selected under the `if __name__ == '__main__'` line .
    * **`green_industry_run_scenarios.py`**: essentially the same as `green_steel_ammonia_run_scenarios.py`, except some changes so that the cement model can be run with the steel model. Some of these changes are outlined in the block comment at the top of the script.
    * **`hopp_tools_industry.py`**: essentially the same as `hopp_tools_cement.py`, see above.
    * **`run_profast_for_steel_coupled.py`**: essentially the same as `run_profast_for_steel.py`, except doesn't sell excess oxygen so it can be used in cement production
* the only file that should be executed is the `green_industry_define_scenarios.py` script. 
* information about the cement plant configurations, assumptions made, sources, etc can be found in the `HOPP/green_concrete` directory scripts
* the `green industry define/run scenarios`, `hopp_tools_industry`, etc. scripts are a bit messy and not super well commented. But I tried to make it clear where changes for cement were made
    * ctrl-f "CEMENT" to see where chanes were made
* I was a little bit sloppy with using the eur2013() and eur2014() conversion functions in the correct places
    * did this because IEAGHG had 2013 cash basis and CEMCAP 2014
    * both sources had pretty similar information, which was why I was drawing numbers from both of them
    * the 2013 and 2014 euro to usd conversion rates were pretty similar, so not sure if this even matters that much 
