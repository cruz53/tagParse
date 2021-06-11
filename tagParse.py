import csv, argparse, logging, psutil, re
from logging.handlers import RotatingFileHandler

###CONSTANTS###
DEBUG = False

#Argument Parser Strings
VERSION = '0.01'
DEFAULT_PLC_LABEL = "PLC1"
CLI_PROGRAM_DESC = \
    """This program handles the batch processing of CSV export data from the LPA RSLogix 5000 tag scheme and prepares it
     for importation into RedLion Edge Controllers for Vail's Lift Data SCADA Network."""
OPEN_ARG_DESC = "This is the RSL Export CSV file to be opened include complete file path"
SAVE_ARG_DESC = "This is the Crimson Import CSV file to be save include complete file path"
PLC_LABEL_DESC = "This sets the plc label used in Crimson's addressing scheme, Default is {}".format(DEFAULT_PLC_LABEL)



def globalOperations():
    logger = logging.getLogger('Debug Log')
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = RotatingFileHandler('debug.log', maxBytes=2000, backupCount=5)
    ch.setFormatter(formatter)
    logger.addHandler(handler)
    parser = argparse.ArgumentParser(description=CLI_PROGRAM_DESC)
    parser.add_argument('-o', '--open', required=True, help=OPEN_ARG_DESC)
    parser.add_argument('-s', '--save', required=True, help=SAVE_ARG_DESC)
    parser.add_argument('-p','--plclabel', default=DEFAULT_PLC_LABEL, help=PLC_LABEL_DESC)
    parsedArgs = parser.parse_args()
    return logger, parsedArgs

logger, parsedArgs = globalOperations()

#Container classes
class RSLNotificationTag(object):
    def __init__(self, type, description, code, number):
        self.number = number
        self.type = type
        self.description = description
        self.code = code

    def __repr__(self):
        rep = 'RSLTag({})'.format(self.description)
        return rep

class RSLTagTableHandler:
    def __init__(self, tagType):
        self.tableType = None
        if tagType in ('Alarm', 'Bypass', 'Fault'):
            self.tableType = tagType
        else:
            logger.debug("Tag type mismatch error")
        self.table = []
        self.index = 0

    def addRow(self, tagType, description, code):
        if not self.tableType:
            logger.debug("Table append while not initialized error")
        elif tagType != self.tableType:
            print("TagType({}), tableType({})".format(tagType, self.tableType))
            logger.debug("<ERROR> Tag and table types mismatch")
        else:
            self.table.append(RSLNotificationTag(tagType, description, code, self.index))
            self.index += 1

class CrimsFlagTypeTag:
    def __init__(self):
        self.name = None # tag name
        self.value = None # source name and internal tag name
        self.extent = None # one item or array
        self.flagTreatAs = None # data types (unsigned int, float, bit array MSB, bit array LSB)
        self.takeBit = None # Select bit in array
        self.manipulate = None # invert or not
        self.access = None # RW, W, R
        self.sim = None # Data simulation expression ?
        self.onWrite = None # Data Action expression ?
        self.hasSP = None # Yes or no ?
        self.label = None # Leave empty or save as name ?
        self.desc = None # Label description
        self.clss = None # Label class ?
        self.formType = None # linked or 2-state ?
        self.formatOn = None # (format / on-format / off) translation expression for on-off state ?
        self.formatOff = None # Second half of the above
        self.colType = None # (General, linked, fixed, 2-state) ?
        self.colorOn = None # (color, on-color, off) color selection for on/off characters and the background
        self.colorOff = None # second half of the above
        self.event1 = None #  Mode: Alarming-Disabled, Active On, Active Off, Change of State
        self.event2 = None #  Mode: Alarming-Disabled, Active On, Active Off, Change of State
        self.trigger1 = None #  Mode: Disabled, Active On, Active Off, Change of State- delay and do Expression Action
        self.trigger2 = None #  Mode: Disabled, Active On, Active Off, Change of State- delay and do Expression Action
        self.secAccess = None # Access Control (for object or on)
        self.secLogging = None #Write Logging- Default for Object, Do Not Log Changes, Log Changes by Users,
                               # Log Changes by Users and Programs

    def applyDefaults(self):
        self.name = None # Will require a new naming convention
        self.value = None # This will be a partial of the RSL code value, Ex. '[PLC1.Fault_Table[7]]' (read by machine)
        self.extent = 0 # Always 0 to indicate pulling single bits off the array
        self.flagTreatAs = "Bit Array Little-Endian" # always this to indicate least significant bit
        self.takeBit = None # Variable to indicate the bit index to examine Ex. 'Bit N'
        self.manipulate = "None" # Always 'None' this is where bit inversion would happen
        self.access = "Read Only" # Always this, not RW or W
        self.sim = "" # Always blank, default and simulated values
        self.onWrite = "" # Always Blank, defines action to be taken when data is changed
        self.hasSP = "No" # Always No, defines if tag has a setpoint
        self.label = None # This will be where i will put the RSL code data
        self.desc = None # This will be where i put the RSL description data
        self.clss = "" # Always blank and currently unused by crimson, clss so not to step on python built in naming
        self.formType = "Two-State" # always this, idiots way of saying boolean
        self.formatOn = ""
        self.formatOff = ""
        self.colType = "Two-State" # always this for same reason as above
        self.colorOn = "Red on Black" # always this to indicate a faulted state
        self.colorOff = "Lime on Black" # always this to indicate non-faulted
        self.event1 = "Disabled" # always this, part of alarm handling
        self.event2 = "Disabled" # always this, part of alarm handling
        self.trigger1 = "Disabled" # always this, part of alarm handling
        self.trigger2 = "Disabled" # always this, part of alarm handling
        self.secAccess = "Default for Object" # Always this part of security settings
        self.secLogging = "Default for Object" # Always this part of security settings

    def __repr__(self):
        rep = "CrimsTagPartial({}, {}, {} ,{})".format(self.name, self.value, self.label, self.desc)
        return rep

class CrimsTagTableHandler:
    def __init__(self):
        self.table = []

    def __repr__(self):
        rep = "CrimsonTagTable with {} entries".format(len(self.table))
        return rep

    def addTag(self, tag):
        self.table.append(tag)

    def buildCSV(self, saveFilename):
        with open(saveFilename, 'w', newline='') as csvExportFile:
            csvExportFile.write("\r\n")
            csvExportFile.write("[Flag.5.2]\r\n")
            csvExportFile.write("\r\n")
            writer = csv.writer(csvExportFile)
            writer.writerow(['Name','Value','Extent','FlagTreatAs','TakeBit','Manipulate','Access','Sim','OnWrite', \
                            'HasSP','Label','Desc','Class','FormType','Format / On','Format / Off','ColType', \
                             'Color / On','Color / Off','Event1 / Mode','Event2 / Mode','Trigger1 / Mode', \
                             'Trigger2 / Mode','Sec / Access','Sec / Logging'])
            for tag in self.table:
                writer.writerow([tag.name, tag.value, tag.extent, tag.flagTreatAs, tag.takeBit, tag.manipulate,\
                                 tag.access, tag.sim, tag.onWrite, tag.hasSP, tag.label, tag.desc, tag.clss, \
                                 tag.formType, tag.formatOn, tag.formatOff, tag.colType, tag.colorOn, \
                                 tag.colorOff, tag.event1, tag.event2, tag.trigger1, tag.trigger2, \
                                 tag.secAccess, tag.secLogging])

#Program Handling Functions
def csvImporter(openFilename):
    with open(openFilename, 'r', newline='') as csvImportFile:
        dialect = csv.Sniffer().sniff(csvImportFile.read(1024))
        csvImportFile.seek(0)
        AlarmTable = RSLTagTableHandler('Alarm')
        BypassTable = RSLTagTableHandler('Bypass')
        FaultTable = RSLTagTableHandler('Fault')
        importReader = csv.reader(csvImportFile, delimiter=',')
        for row in importReader:
            if len(row) >= 6 and len(row[3]) > 0 and len(row[5]) > 0:
                if row[2] == 'Alarm_Table':
                    t = re.search(r"(\w+)_Table", row[2])
                    AlarmTable.addRow(t.group(1), row[3], row[5])
                    if DEBUG: print("Alarm table populated with ({}, {}, {})".format(row[2], row[3], row[5]))
                elif row[2] == 'Bypass_Table':
                    t = re.search(r"(\w+)_Table", row[2])
                    BypassTable.addRow(t.group(1), row[3], row[5])
                    if DEBUG: print("Bypass table populated with ({}, {}, {})".format(row[2], row[3], row[5]))
                elif row[2] == 'Fault_Table':
                    t = re.search(r"(\w+)_Table", row[2])
                    FaultTable.addRow(t.group(1), row[3], row[5])
                    if DEBUG: print("Fault table populated with ({}, {}, {})".format(row[2], row[3], row[5]))
    return AlarmTable, BypassTable, FaultTable

def RSLtoCrimsHandler(RSLTag):
    newTag = CrimsFlagTypeTag()
    newTag.applyDefaults()
    # Name Field
    specCharRegex = re.compile(r"\W+", re.I | re.A)
    newTag.name = specCharRegex.sub('_', RSLTag.code)
    # Value Field
    RSLCodeFailedRegex = re.compile(r"(\w+)_Table\W\d{1,2}\W$", re.I | re.A)
    RSLCodeParsingRegex = re.compile(r"(\w+)_Table\W(\d{1,2})\W\.(\d{1,2})", re.I | re.A)
    RSLCodeMatchObj = RSLCodeParsingRegex.match(RSLTag.code)
    RSLCodeFailedMatchObj = RSLCodeFailedRegex.match(RSLTag.code)
    if RSLCodeMatchObj and not RSLCodeFailedMatchObj:
        newTag.value = "[{}.{}_Table[{}]]".format(parsedArgs.plclabel, RSLCodeMatchObj.group(1), RSLCodeMatchObj.group(2))
        # Take Bit Field
        newTag.takeBit = "Bit {}".format(RSLCodeMatchObj.group(3))
        # Label Field
        newTag.label = RSLTag.code
        # Description Field
        newTag.desc = RSLTag.description
        return newTag
    elif RSLCodeFailedMatchObj and not RSLCodeMatchObj:
        return None
    else:
        print("<ERROR> Fallthrough {} {}".format(RSLCodeMatchObj, RSLCodeFailedMatchObj))

def main():
    openFilename = parsedArgs.open
    saveFilename = parsedArgs.save
    alarmTable, bypassTable, faultTable = csvImporter(openFilename)
    CrimsTags = CrimsTagTableHandler()
    for table in (alarmTable.table, bypassTable.table, faultTable.table):
        for tag in table:
            newTag = RSLtoCrimsHandler(tag)
            if newTag: CrimsTags.addTag(newTag)
    print(CrimsTags)
    CrimsTags.buildCSV(saveFilename)
    if DEBUG: print('RAM memory % used:', psutil.virtual_memory()[2])


if __name__ == "__main__": main()