"""
Sparki library communicating with ESP32 over UDP socket.
Yoshiro Fujita, 9/13/2022
"""
import socket, logging, time



class CircularBuffer:
    def __init__(self, length):
        self.data = [0] * length
        self.length = length
        self.index = 0

    def add(self, data):
        self.data[self.index] = data
        self.index += 1
        if self.index >= self.length:
            self.index = 0

    def avg(self):
        if self.data.count(0) == self.length:
            return 100
        else:
            return sum(self.data) / (self.length - self.data.count(0))


class ESP32:
    def __init__(self, name=None, ip=None, port=3141):
        """Create custom logger"""
        self.logger = logging.getLogger(__name__)
        c_handler = logging.StreamHandler()
        c_format= logging.Formatter(fmt='%(asctime)s.%(msecs)03d:   %(message)s', datefmt='%H:%M:%S')
        c_handler.setLevel(logging.DEBUG)
        c_handler.setFormatter(c_format)
        self.logger.addHandler(c_handler)
        self.logger.setLevel(logging.INFO)

        
        self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.socket.settimeout(1)
        self.timeout_errors = CircularBuffer(5)
        self.last_timeout = time.time()
        self.socket.setblocking(1)
        self.name = name
        self.ip = ip
        self.port = port
        
        if name != None:
            if ".local" not in name:
                self.name += ".local"
                
            self.ip = socket.gethostbyname(self.name)
            self.address = (self.ip, port)
        elif ip != None:
            self.address = (ip, port)
        else:
            raise Exception("Require valid host or IP.")
        self.logger.info(f"ESP32 Address set to {self.address}")



    def udp_send(self, msg):
        self.socket.sendto(msg.encode("utf-8"), self.address)
        self.logger.debug(f"Sent {msg}")

    def udp_get(self, timeout=0.2):
        self.socket.settimeout(timeout)
        self.logger.debug(f"Waiting to receive...")
        try:
            msg = self.socket.recvfrom(300)
            self.logger.debug(f"Received {msg}")
            return msg[0].decode("utf-8")
        except TimeoutError:
            now = time.time()
            self.timeout_errors.add(now - self.last_timeout)
            self.last_timeout = now
            period = self.timeout_errors.avg()
            self.logger.error(f"Timeout Error. Timeout = {timeout:.1f} seconds (avg timeout frequency = 1 per {period:.3f} seconds)")
            if period < 0.100:
                raise Exception("Timeouts occurring too frequently. Try resetting Sparki.")
            return 0


    def set_logger_level(self, level):
        level_dict = { "debug"   : logging.DEBUG,
                       "info"    : logging.INFO,
                       "warning" : logging.WARNING,
                       "error"   : logging.ERROR }
        self.logger.setLevel(level_dict[level.lower()])


class Sparki(ESP32):
    def __init__(self, name=None, ip=None, port=3141):
        ESP32.__init__(self, name, ip, port)
        self.command_count = 0
        self.command_time = 0
        self.stop()

    def send(self, msg):
        self.udp_send(msg)

    def get(self, msg, timeout=1):
        t0 = time.time()
        self.send(msg)
        response = self.udp_get(timeout)
        self.command_time += time.time() - t0
        self.command_count += 1
        if type(response) == str and "NACK" in response:
            raise Exception("ESP-Sparki NACK: Try resetting Sparki.")
            return 0
        return response

    """ Sparki Outputs """  
    def move(self, distance):
        msg = "V"
        forward = ["forward", "f"]
        backward = ["backward", "b"]
        stop = ["stop", "s"]

        indef = True

        if type(distance) == str:
            if distance.lower() in forward:
                msg += "1"
            elif distance.lower() in backward:
                msg += "-1"
            elif distance.lower() in stop:
                msg += "0"
            else:
                raise Exception("Do not recognize linear movement parameter. Must be FORWARD, BACKWARD, or STOP")
        elif type(distance) == int or type(distance) == float:
            msg = "v"
            msg += str(round(distance,2))
            indef = False
        else:
            raise Exception("Do not recognize linear movement parameter. Must be FORWARD, BACKWARD, or STOP")
        
        if indef:
            self.send(msg)
        else:
            r = self.get(msg, max(abs(distance) * 0.5, 1))

    def turn(self, angle):
        msg = "T"
        right = ["right", "r"]
        left = ["left", "l"]
        stop = ["stop", "s"]

        indef = True
        
        if type(angle) == str:
            if angle.lower() in right:
                msg += "1"
            elif angle.lower() in left:
                msg += "-1"
            elif angle.lower() in stop:
                msg += "0"
            else:
                raise Exception("Do not recognize turning parameter. Must be RIGHT, LEFT, or STOP")
        elif type(angle) == int or type(angle) == float:
            msg = "t"
            msg += str(round(angle,2))
            indef = False
        else:
            raise Exception("Do not recognize turning parameter. Must be RIGHT, LEFT, or STOP")
        
        if indef:
            self.send(msg)
        else:
            self.get(msg, max(abs(angle) * 0.05, 1))
    
    def stop(self):
        self.send("X")

    def motors(self, speeds):
        if len(speeds) < 2:
            self.logger.error("Not enough speeds specified")
        else:
            if speeds[0] < -100:
                speeds[0] = -100
            elif speeds[0] > 100:
                speeds[0] = 100
                
            if speeds[1] < -100:
                speeds[1] = -100
            elif speeds[1] > 100:
                speeds[1] = 100
                
            msg = "m"
            if speeds[0] == None:
                speeds[0] = 400
            if speeds[1] == None:
                speeds[1] = 400
            msg += str(int(speeds[0])+100)
            msg += "."
            msg += str(int(speeds[1])+100)
        
        self.send(msg)
        
    
    def gripper(self, distance):
        msg = 'G'
        g_open = ["open", "o"]
        g_close = ["close", "c"]
        g_stop = ["stop", "s"]

        indef = True

        if type(distance) == str:
            if distance.lower() in g_open:
                msg += "1"
            elif distance.lower() in g_close:
                msg += "-1"
            elif distance.lower() in g_stop:
                msg += "0"
            else:
                raise Exception("Do not recognize gripper parameter. Must be OPEN, CLOSE, or STOP")
        elif type(distance) == int or type(distance) == float:
            msg = "g"
            msg += str(round(distance, 2))
            indef = False
        else:
            raise Exception("Do not recognize gripper parameter. Must be OPEN, CLOSE, or STOP")    

        if indef:
            self.send(msg)
        else:
            self.get(msg, max(abs(distance), 1))

    def servo(self, angle):
        self.send("s" + str(int(angle)))

    def led(self, color):
        if len(color) < 3:
            self.logger.error("Need RED, GREEN, and BLUE values")
        else:
            msg = "dr" + str(int(color[0])) + "g" + str(int(color[1])) + "b" + str(int(color[2]))
            self.send(msg)

    def beep(self, frequency = 110, duration = 0.2):
        msg = "e1f" + str(int(frequency)) + "d" + str(round(duration,3)) 
        self.send(msg)

    def nobeep(self):
        self.send("e0")
        

    """ Sparki Inputs """
    def ping(self, timeout=0.5):
        r = self.get("p", timeout)
        try:
            distance = float(r)
        except:
            self.logger.error("Received non-numeric value from ping()")
            distance = 54321
        if distance < 0:
            distance = 54321
        return distance

    def lidar(self, timeout=0.1):
        r = self.get("L", timeout)
        try:
            distance = float(r)/10.0
        except:
            self.logger.error("Received non-numeric value from lidar()")
            distance = 54321
        if distance < 0:
            if distance == -13:
                raise Exception("LIDAR did not boot");
            distance = 54321
        return distance

    def line(self, as_list = False, timeout=0.1):
        r = self.get("n", timeout)
        try:
            lines = r.split()
        except:
            self.logger.error("Unexpected line vector response")
            lines = [0, 0, 0, 0, 0]
        if as_list:
            return [int(lines[i]) for i in range(len(lines))]
        else:
            keys = ["edge left", "left", "center", "right", "edge right"] 
            return {keys[i]: float(lines[i]) for i in range(min(len(lines), len(keys)))}
        
    def light(self, as_list = False, timeout=0.1):
        r = self.get("l", timeout)
        try:
            lights = r.split()
        except:
            self.logger.error("Unexpected light vector response")
            lights = [0, 0, 0, 0, 0]
        if as_list:
            return [int(lights[i]) for i in range(len(lights))]
        else:
            keys = ["left", "center", "right"]
            return {keys[i]: float(lights[i]) for i in range(min(len(lights), len(keys)))}

    def accel(self, as_list = False, timeout=0.05):
        r = self.get("a")
        try:
            accels = r.split()
        except:
            self.logger.error("Unexpected line vector response")
            accels = [0, 0, 0, 0, 0]
        if as_list:
            return [int(accel[i]) for i in range(len(accels))]
        else:
            keys = ["x", "y", "z"]
            return {keys[i]: float(accels[i])/1000.0 for i in range(min(len(accels), len(keys)))}
            
    def mag(self, as_list = False, timeout=0.05):
        r = self.get("c", timeout)
        try:
            mags = r.split()
        except:
            self.logger.error("Unexpected line vector response")
            mags = [0, 0, 0, 0, 0]
        if as_list:
            return [int(mags[i]) for i in range(len(mags))]
        else:
            keys = ["x", "y", "z"]
            return {keys[i]: float(mags[i])/1000.0 for i in range(min(len(mags), len(keys)))}

    def battery(self):
        r = self.get("b")
        return r

    def set_comm_timeout(self, t):
        self.send("i" + str(t*1000))
