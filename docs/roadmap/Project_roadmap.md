# Project roadmap

## Principal goals for 2024

The main goal for 2024 is to get __Cluster Management Toolkit for Kubernetes__ (__CMT__)
ready for mainstream adoption. The code quality should be such that it does not
scare off first time contributors. It must be at least _theoretically possible_
to distribute __CMT__ as a part of a Linux distribution
(there's obviously no guarantee that any distro will distribute it).

## Q1 roadmap
* _General_:
    * Start writing release notes.
    * tests: Achieve 25% test coverage for `*.py`.
* _cmtadm_:
    * Support for virtualised nodes. It should be possible to create clusters
      with a combination of virtualised and bare metal hosts. It should also be
      possible to clusters that only have virtualised nodes. There should be three
      base types of VMs:
        * DHCP/routing (mandatory on hosts that run VMs; not part of the cluster. Minimal VM).
        * Control plane (optional; the control plane can be bare metal).
        * Node (optional; nodes can be bare metal).
      Node groups can then be used to specify different VM images in case
      a heterogenous cluster is wanted.
    * Every bare metal host that runs virtual machines will run a DHCP/routing VM.
* _cmu_:
    * The User Interface should allow for, and in most cases default to, asynchronous data updates.
    * To accomodate for asynchronous updates we also need to figure out how to deal
      with updates happening while the user is interacting with the data (such as
      stepping through a list or similar). This includes:
        * Defining an idle state.
        * Not jumping to the beginning of the list every time the data is refreshed
          if the sort order hasn't changed unless the UI is idle.
        * Dimming out deleted items until the UI is idle or hard refresh is triggered.
        * Making dimmed out entries unselectable.
        * Ignoring deleted entries when executing actions on selected items.
        * Adding new items to the bottom of the list unless the UI is idle.
        * Not resorting the list until the UI is idle or hard refresh is triggered.

## Q2 roadmap
* _Accessibility_:
    * Ensure that the Colour Vision Deficiency theme covers all relevant data.
      Using colour coding in conjunction with CVD is acceptable, but only when important
      information (severity, etc.) is conveyed through other means.
    * Provide a high-contrast theme.
* _General_:
    * Refactor libraries in a way that makes a __CMT__ release possible. This includes:
        * No circular dependencies.
        * No logging from libraries; raise custom exceptions that include extra exception data
          (formatted exception messages), no use of sys.exit() from libraries.
    * tests: Achieve 40% test coverage for `*.py`.
* _cmu_:
    * UI refactoring: data viewers (the logpad in genericinfoloop as well as
      the containerinfoloop log viewer) should be merged. Having two implementation
      that mostly do the same thing doesn't make any sense.

## Q3 roadmap
* _General_:
    * First release.
    * Distribute as (Note: requires legal process):
        * Source code.
        * Debian package.
        * Possibly via PIP?
    * By this point we should be able to get the OpenSSF Best Practice passing badge.
    * tests: Achieve 50% test coverage for `*.py`.
* _cmu_:
    * UI refactoring: Use the generic input handler from curses helper for all input.
    * UI refactoring: Unified helptext generation.
    * General refactoring: Start working on turning _cmu_ into a generic UI framework
      that takes YAML files that describe list, info, and data (logpad) views.
      The descriptions should include helpers to use to fetch data,
      helpers to use to process that data, a list of actions that can be performed
      on that data, as well as information about what, if any, relationships the data
      has with data in other info views.

## Q4 roadmap
* _Project_:
    * Write all documentation needed to meet silver criteria for OpenSSF Best Practices.
      Note that several of the requirements for silver and gold criteria makes meeting
      all criteria unlikely, but we should still do our best.
* _General_:
    * Go through all input helpers, formatters, etc., to see which, if any, we can
      merge.
    * By the end of Q4 all functions, classes, and methods should have docstrings
      and type hints.
    * tests: Achieve 60% test coverage for `*.py`.
* _cmu_:
    * Continue, hopefully conclude, the general refactoring, enabling new _cmt_ functionality.
* _cmt_:
    * Once the _cmu_ refactoring has taken place we should be in a good place to
      reuse most of the helpers to implement `cmt get OBJECT`, `cmt describe OBJECT`,
      etc.
