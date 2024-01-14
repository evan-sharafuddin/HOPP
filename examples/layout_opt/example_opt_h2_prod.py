from hopp.simulation import HoppInterface

hi = HoppInterface("examples/inputs/layout_opt/example_opt_h2_prod.yaml")
hi.simulate(25)
