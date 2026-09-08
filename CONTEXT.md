# MxLIVE Domain Context

Macromolecular Crystallography (MX) Laboratory Information Virtual Environment for managing synchrotron crystallography beamline experiments, sample logistics, and automated data collection at the Canadian Light Source. Extends the foundational synchrotron LIMS primitives defined in `basic-live`.

## Language

### Physical Containment & Logistics

**Dewar**:
A vacuum-insulated cryogenic shipping vessel that transports sample containers under liquid nitrogen temperatures to and from the facility.
_Avoid_: Cryo-shipper, Dry shipper, Shipper, CX100.

**Puck**:
A standardized cylindrical cryo-container holding an indexed set of pins for loading into a beamline automounter.
_Avoid_: Cassette, Carousel, Magazine, Tray.

**Pin**:
A standardized magnetic base with a mounted micro-loop or mesh holding an individual macromolecular crystal or cryo-protected specimen.
_Avoid_: Base, Loop, Crystal mount, Specimen.

**Crystallization Plate**:
A multi-well container used for crystal growth and direct in situ diffraction screening on the beamline.
_Avoid_: Tray, SBS Plate, Screening block.

**Well**:
An indexed chamber or droplet position within a Crystallization Plate holding crystallization solution and crystals for in situ exposure.
_Avoid_: Drop, Subwell, Cavity.

### Experimental Workflows & Data

**Rastering**:
A 2D X-ray grid scan across a sample loop or mesh to identify crystal coordinates, diffracting boundaries, and diffraction hotspots prior to data collection.
_Avoid_: Grid scan, Mesh scan, Crystal locating.

**Screening**:
A quick test collection of one or a few low-dose diffraction images used to evaluate crystal quality, resolution limit, indexing, and ice formation before full data collection.
_Avoid_: Test exposure, Characterization shot, Test diffraction.

**MX Dataset**:
A complete, rotational series of X-ray diffraction images collected across an angular range for macromolecular structure determination.
_Avoid_: Full collection, Wedge, Data run, Diffraction run.

**MAD Scan**:
A fluorescence and energy scan measured across an anomalous absorption edge to determine anomalous scattering factors (\(f'\) and \(f''\)) for experimental phasing.
_Avoid_: Energy scan, Fluorescence scan, Edge scan, Phasing scan.

**XRF Spectrum**:
An X-ray fluorescence emission spectrum measured from a sample to identify elemental composition and bound heavy atom scatterers.
_Avoid_: Fluorescence spectrum, Metal scan, Elemental scan.

**Analysis Report**:
The automated or manual data reduction, integration, and phasing metrics (such as resolution limits, completeness, \(R_{\text{merge}}\), and \(I/\sigma\)) generated for a dataset and formatted dynamically for display.
_Avoid_: Autoprocessing Report, Processing Result, Pipeline Output, Analysis Log.

### Operational Access Modes

**Access Mode**:
The operational paradigm under which beamtime is allocated and utilized on a beamline.
_Avoid_: Collection Mode, Shift Type, Operation Type, Visit Type.

**Remote**:
An Access Mode where beamline instrumentation and data collection are steered remotely by users over a secure network connection.
_Avoid_: Remote access, Off-site collection.

**Mail-in**:
An Access Mode where sample dewars are shipped to the facility and handled entirely by facility staff on behalf of the project.
_Avoid_: Service collection, Staff collection, Mail-in service.

**On-site**:
An Access Mode where researchers are physically present in the beamline hutch to mount samples and operate instrumentation.
_Avoid_: Local, In-person, Hutch collection.

**Unattended**:
An Access Mode where data collection is executed autonomously by beamline robotics and automated acquisition queues without active human steering.
_Avoid_: Autonomous collection, Robot run, Batch mode.

### Beamline Automation & Systems

**MxDC**:
The macromolecular data collection software controlling beamline instrumentation that synchronizes sample information, session status, and experiment metadata with MxLIVE.
_Avoid_: Data Collector, Acquisition Client, Beamline Control.

**Data Proxy**:
An independent service that validates ephemeral tokens issued by MxLIVE and streams raw diffraction files, scans, and report assets directly from facility storage.
_Avoid_: Storage Gateway, File Server, Download Broker.
