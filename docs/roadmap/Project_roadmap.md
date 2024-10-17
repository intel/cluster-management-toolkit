# Project roadmap

## Principal goals for 2024

The main goal for 2024 is to get __Cluster Management Toolkit for Kubernetes__ (__CMT__)
ready for mainstream adoption. The code quality should be such that it does not
scare off first time contributors. It must be at least _theoretically possible_
to distribute __CMT__ as a part of a Linux distribution
(there's obviously no guarantee that any distro will distribute it).

Note: the test coverage for `*.py` will drop whenever code
is moved from `cmt`, `cmtadm`, `cmu`, and `cmtinv` to `*.py`, until
tests have been added for the moved code.

## Q1 roadmap
* _General_:
    * [x] First release.
    * [x] OpenSSF Best Practice passing badge.
    * [x] tests: Achieve 30% test coverage for `*.py`.
* _cmtadm_:
    * [x] Support for virtualised nodes. It should be possible to create clusters
      with virtualised nodes.
    * [x] DHCP for the virtualised nodes is handled by the libvirt default network.
* _cmu_:
    * [x] The User Interface should allow for, and in most cases default to, asynchronous data updates.
    * [x] To accomodate for asynchronous updates we also need to figure out how to deal
      with updates happening while the user is interacting with the data (such as
      stepping through a list or similar). This includes:
        * [x] Defining an idle state.
        * [x] Not jumping to the beginning of the list every time the data is refreshed
          if the sort order hasn't changed unless the UI is idle.
        * [x] Dimming out deleted items until the UI is idle or hard refresh is triggered.
        * [x] Making dimmed out entries unselectable.
        * [x] Ignoring deleted entries when executing actions on selected items.
        * [x] Not resorting the list until the UI is idle or hard refresh is triggered.

## Q2 roadmap

Due to severe re-prioritising the Q2 roadmap almost no base-work was done on the project;
the roadmap has, for now, been pushed back one quarter, but further slips are likely.

## Q3 roadmap
* _Accessibility_:
    * [ ] Ensure that the Colour Vision Deficiency theme covers all relevant data.
      Using colour coding in conjunction with CVD is acceptable, but only when important
      information (severity, etc.) is conveyed through other means.
    * [ ] Provide a high-contrast theme.
* _General_:
    * [ ] Refactor libraries in a way that makes a __CMT__ release possible. This includes:
        * [ ] No circular dependencies.
        * [ ] Rewrite all logging to use Python's builtin logging and register a MemoryHandler;
              this way we get flushing whenever the severity is high enough.
    * [ ] Register KeyboardInterrupt handlers in all executables to do proper shutdown
          and print helpful messages.
    * [ ] tests: Achieve 45% test coverage for `*.py`.
* _cmu_:
    * [ ] UI refactoring: data viewers (the logpad in genericinfoloop as well as
      the containerinfoloop log viewer) should be merged. Having two implementation
      that mostly do the same thing doesn't make any sense.
    * [ ] Use __python3-pygments__ for syntax highlighting.
    * [ ] Use __python3-jinja2__ for view-file templating.

## Q4 roadmap
* _General_:
    * [ ] Distribute as:
        * [ ] Source code.
        * [ ] Debian package.
        * [ ] Possibly via PIP?
    * [ ] tests: Achieve 55% test coverage for `*.py`.
* _cmu_:
    * [ ] UI refactoring: Use the generic input handler from curses helper for all input.
    * [ ] UI refactoring: Unified helptext generation.
    * [ ] General refactoring: Start working on turning _cmu_ into a generic UI framework
      that takes YAML files that describe list, info, and data (logpad) views.
      The descriptions should include helpers to use to fetch data,
      helpers to use to process that data, a list of actions that can be performed
      on that data, as well as information about what, if any, relationships the data
      has with data in other info views.

## Q1/2025 roadmap
* _Project_:
    * [ ] Write all documentation needed to meet silver criteria for OpenSSF Best Practices.
      Note that several of the requirements for silver and gold criteria makes meeting
      all criteria unlikely, but we should still do our best.
* _General_:
    * [ ] Go through all input helpers, formatters, etc., to see which, if any, we can
      merge.
    * [ ] All functions, classes, and methods should have docstrings and type hints.
    * [ ] tests: Achieve 65% test coverage for `*.py`.
* _cmu_:
    * [ ] Continue, hopefully conclude, the general refactoring, enabling new _cmt_ functionality.
* _cmt_:
    * [ ] Once the _cmu_ refactoring has taken place we should be in a good place to
      reuse most of the helpers to implement `cmt get OBJECT`, `cmt describe OBJECT`,
      etc.

## Backlog
* _cmtadm_:
    * [ ] Support for clusters with virtualised control planes.
    * [ ] Support for having multiple different VM-hosts in the same cluster.
