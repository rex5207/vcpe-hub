# Firewall

A simple firewall based on ryu.


# Run-Up Firewall
```sh
ryu-manager l2switch.py simple_firewall.py flow_monitor.py
```

# API Using Example

**GET /api/firewall/acl**

- tells us the current block list
- example:

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
  - example:
  ```sh
  {
      "ruleAction": "add",
      "srcIP": "10.0.0.1",
      "dstIP": "10.0.0.2",
      "protocol": "HTTP"
  }
  ```
- example:
```sh
$ curl -H "Content-Type: application/json" -X PUT -d '{"ruleAction":"add","srcIP":"10.0.0.1","protocol":"HTTP","dstIP":"10.0.0.2"}' http://127.0.0.1:8080/api/firewall/acl/knownport
```
