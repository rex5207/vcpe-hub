# Firewall

A simple firewall based on ryu.

# Run-Up
```sh
ryu-manager l2switch.py simple_firewall.py flow_monitor.py
```

### Architecture
```sh
├── README.md       # document
├── config          # l2switch setting
│   ├── __init__.py
│   ├── settings.py
├── data.py
├── flow_monitor.py # use to track blocking rule
├── l2switch.py     # forwarding function
├── route           # API route
│   ├── __init__.py
│   ├── urls.py     
├── simple_firewall.py # main firewall function
```



# API Using Example

**GET /api/firewall/acl**

- tells us the current block list
- api use example:

```sh
# it will return current blocking list
$ curl -GET http://127.0.0.1:8080/api/firewall/acl
{"flow":[
  {"tranPort": 80,
   "ipSrc": "10.0.0.1",
   "tranProtocol": "TCP",
   "ipDst": "10.0.0.2"},
  {"tranPort": 443,
   "ipSrc": "8.8.8.8",
   "tranProtocol": "TCP",
   "ipDst": null}
  ]
}
```

**PUT /api/firewall/acl/knownport**
- set blocking rule based on a certain known port
- takes JSON:
  - ruleAction: "add" or "delete" to specify the action of rule
  - dstIP: destination IP you want to block
  - srcIP: source IP you want to block
  - protocol: A certain known protocol you want to block
    - "HTTP", "FTP", "SSH", "TELNE", "HTTPS", "SMTP", "POP3", "IMAP"   
- api use example:
```sh
$ curl -H "Content-Type: application/json" -X PUT -d '{"ruleAction":"add","srcIP":"10.0.0.1","protocol":"HTTP","dstIP":"10.0.0.2"}' http://127.0.0.1:8080/api/firewall/acl/knownport
```
- use case:
  1. block a certain protocol for all hosts, eg. FTP
  ```sh
  {
      "ruleAction": "add",
      "srcIP": "",
      "dstIP": "",
      "protocol": "HTTP"
  }
  ```
  2. block a certain source ip, eg. `10.0.0.1`
  ```sh
  {
      "ruleAction": "add",
      "srcIP": "10.0.0.1",
      "dstIP": "",
      "protocol": ""
  }
  ```
  3. to let certain user cannot use a certain protocol
  ```sh
  {
      "ruleAction": "add",
      "srcIP": "10.0.0.1",
      "dstIP": "",
      "protocol": "FTP"
  }
  ```
