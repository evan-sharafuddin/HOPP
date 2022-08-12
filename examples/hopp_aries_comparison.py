import json
import pandas as pd
import matplotlib.pyplot as plt

# Import HOPP results
filepath = 'results/' + 'yearlong_outputs.json'
hopp_results = pd.read_json(filepath)
hopp_results.index = pd.date_range(start="2021-06-30 23:00:00", periods=8760, freq="h")

# Import ARIES generation
filepath = 'resource_files/' + 'yearlong_aries_generation.csv'
aries_gen = pd.read_csv(filepath)
aries_gen.index = pd.date_range(start="2021-06-30 23:00:00", periods=8760, freq="h")
aries_gen.columns = ['Solar','Wind']

# Parse results
hopp_solar = hopp_results.loc[:,'pv generation (kW)']
hopp_wind = hopp_results.loc[:,'wind generation (kW)']
aries_solar = aries_gen.loc[:,'Solar']
aries_wind = aries_gen.loc[:,'Wind']

# Zero out negative solar from ARIES
zero_inds = aries_solar.values<0
aries_solar.iloc[zero_inds] = 0

# Plot results
start = '2021-07-01'
end = '2022-07-01'
mod_label = 'HOPP Modeling'
act_label = 'Actual Power Output'
plt.subplot(2,1,1)
plt.plot(hopp_solar.index,hopp_solar.values,label=mod_label)
plt.plot(aries_solar.index,aries_solar.values,label=act_label)
plt.ylabel("First Solar 430 kW PV Generation [kW]")
plt.legend()
plt.xlim([pd.to_datetime(start),pd.to_datetime(end)])
plt.subplot(2,1,2)
plt.plot(hopp_wind.index,hopp_wind.values,label=mod_label)
plt.plot(aries_wind.index,aries_wind.values,label=act_label)
plt.ylabel("GM 1.5 MW generation [kW]")
plt.legend()
plt.xlim([pd.to_datetime(start),pd.to_datetime(end)])
plt.show()