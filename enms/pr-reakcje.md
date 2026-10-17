# MCP server: reaction tools (conversion, equilibrium, reaction sets, Gibbs compounds)

## Motivation

The MCP server can add every reactor type (`dwsim_unitop_add`: ConversionReactor, EquilibriumReactor,
GibbsReactor, CSTR, PFR), but no tool defines a reaction or tells a Gibbs reactor which compounds to minimise
over. Over MCP alone a conversion or equilibrium reactor has an empty `DefaultSet`, and a Gibbs reactor fails with
"The Element Matrix is not defined". The assistant's HTTP API already covers reactions (`/api/add-reaction` in
`DWSIM.Extensions.AI.Assistant/Server.vb`), and the readme says the MCP server and that API go together, so this
looks like a gap rather than a choice.

We use the server for combustion and flue-gas heat balances (energy audits), which need conversion reactions,
and for equilibrium checks of reformer and reduction gases.

## Tools

New file `tools/DWSIM.MCPServer/Tools/Reactions/ReactionTools.cs`, registered in `Program.cs` (2 lines).

| Tool | Does |
|---|---|
| `dwsim_reaction_add_conversion` | `DefineConversionReaction` and adds it to a set (`DefaultSet` unless named; a missing set is created). Conversion in %, number or expression in T. Default phase Vapor, as in `/api/add-reaction`. |
| `dwsim_reaction_add_equilibrium` | `DefineEquilibriumReaction`; empty `lnkeq_expression` = K from Gibbs energies of formation. Default basis fugacity. |
| `dwsim_reactionset_create` | An empty set, for two reactors that need different reactions (`dwsim_unitop_set {"ReactionSetID": ...}`). |
| `dwsim_reaction_list` | Reactions (equation, stoichiometry, base compound, phase, expression, heat of reaction, mass balance) and sets with their members; works on loaded flowsheets too. |
| `dwsim_reactor_set_compounds` | Sets `ComponentIDs` of a Gibbs reactor, clears `InitialEstimates`/`PreviousSolution` (sized for the old list) and calls `CreateElementMatrix()`. Needs the feed connected and specified. |

The add tools return the created reaction, including `heat_of_reaction_kJ_kmol` (kJ/kmol of base compound) and
`mass_balance_kg_kmol`, so a client can check the reaction before solving.

The steady-state paragraph of the `initialize` instructions gets one step: reactions after the compounds, and
`dwsim_reactor_set_compounds` for a Gibbs reactor (3 lines in `JsonRpcDispatcher.cs`).

## Checks before a reaction is created

The engine accepts all of these without an error; the tools refuse them with an `ArgumentException` that says
what to do:

- a compound not in the flowsheet. `CalcReactionStoichiometry` skips it when it sums the enthalpies of
  formation, so the heat of reaction comes out wrong with no message (`FlowsheetBase.vb`, the two
  `If Not Options.SelectedComponents.ContainsKey(c.Key) Then Continue For`);
- an element imbalance, computed from the compounds' `Elements` (the error lists the difference per element);
  pseudo-compounds without a formula are not checked;
- a base compound that is missing from the stoichiometry or is a product;
- an unknown phase or equilibrium basis (the engine's `Select Case` would silently keep the default);
- a duplicate reaction or set name; a coefficient that is zero or not a number.

## Test

The repository has no test project for the MCP server (the projects in `tests/` cover the engine and the
Fluent API), so the tools were checked end to end over HTTP against a container built from this branch:

- Combustion of CH4 0.6, C2H6 0.05, CO 0.2, H2 0.15 mol/s at air ratio 1.6, conversion 100%, outlet 150 °C,
  Raoult's law: outlet composition and heat duty equal to the same case built with Automation3 on macOS
  (max |Δx| 4e-17, Q −597.507351 kW, |ΔQ| below 1e-6 relative).
- Heats of reaction within 0.1% of tabulated LHV at 25 °C (CH4 −802 618, C2H6 −1 428 642, CO −282 980,
  H2 −241 814 kJ/kmol).
- Water-gas shift at 700 K and 1 atm, Peng-Robinson, K from Gibbs energies: equilibrium reactor K = 9.3856;
  Gibbs reactor after `dwsim_reactor_set_compounds` agrees within 1e-4 mole fraction (before it, "The Element
  Matrix is not defined").
- Steam reforming in a Gibbs reactor (CH4/H2O 1:3, 850 °C, 20 bar): CH4 0.0274, H2O 0.3238, CO 0.0933,
  CO2 0.0551, H2 0.5004, Q 477.77 kW.
- Every refusal listed above.

## Not in this PR

- Kinetic and heterogeneous catalytic reactions (CSTR, PFR), and editing or deleting reactions.
- Two observations we will report separately: `composition` in `dwsim_stream_add_material` and
  `dwsim_stream_set_conditions` sets compound mass flows in kg/s and so overrides the total flow given in the
  same call; and a Gibbs reactor case (water-gas shift, 700 K, feed x_CO 0.5000216) that converts fully without
  an error in the Linux container while the same feed on macOS reaches equilibrium.
