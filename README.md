# Barrister

Barrister lets you write well documented services that can be consumed from a variety of languages.  The
basic steps are:

* Write an IDL file (See: http://barrister.bitmechanic.com/docs.html)
* Run the `barrister` tool to convert the IDL file to JSON and HTML files
* Install the language binding for the lanuage you're writing the server in 
  (See: http://barrister.bitmechanic.com/download.html)
* Write a server that implements the interfaces in the IDL

This project contains the core `barrister` command line tool as well as the Python bindings.

## Installation

### Install

I suggest installing pip.  All Python distributions that I'm aware of ship with `easy_install`, so if 
you don't have `pip` yet, you can try:

    easy_install pip
    
Then you simply run:

    pip install barrister
    
You may need to be root to install packages globally, in which case you should `su` to root or use `sudo`:

    sudo pip install barrister

### Dependencies

If you're using Python 2.6 or later, you're good to go.  Python 2.5 users will need to:

    pip install simplejson
    
Python 2.3 and 2.4 users will need to:

    pip install uuid simplejson

## Tutorial
    
In this tutorial we'll use the Python Barrister bindings to write a simple contact management service.
The [examples directory](https://github.com/coopernurse/barrister/blob/master/examples) contains the
resulting IDL, client, and server.  Please refer to these files as we go along:

* `contact.idl` - IDL file
* `contact_server.py` - Implementation of the IDL using Python and [bottle](http://bottlepy.org/)
* `contact_client.py` - Client program that demonstrates how to call the service, trap errors, and 
  uses batches

### Running the example

If you don't mind downloading the repo, this is an easy way to try it out.  On Mac OS or Linux:

    git clone git://github.com/coopernurse/barrister.git
    cd barrister/examples
    python contact_server.py > /dev/null &
    python contact_client.py
    fg      (to foreground the server)
    ctrl-c  (to quit the server)
    
Try running in a few times, and you'll see the output change as different contacts are deleted.

### Write the IDL

First we have to write our interface definition, which is in `contact.idl`.  With the comments we have
a single interface defined:

    interface ContactService {
        put(contact Contact) string
        get(contactId string, userId string) Contact
        getAll(userId string) []Contact
        delete(contactId string, userId string) bool
    }

Notice that you can use structs as parameters or return types.  `[]` denotes an array.  The type 
follows the identifier.

Structs can reference other structs or enums, in addition to primitive types.  Notice that the `Contact`
has an array of `Phone` objects:

    struct Contact {
      contactId string
      userId    string
      firstName string
      lastName  string
      email     string
      phones    []Phone
    }    

I've checked the generated `contact.json` into git, but this is an artifact of running the `barrister`
tool.  You could try regenerating it by running:

    barrister -j contact.json contact.idl
    
If you want the HTML documentation for the interface, simply add the `-d` option:

    barrister -d contact.html -j contact.json contact.idl

### Understanding the implementation

Take a moment to read the `contact_client.py` and `contact_server.py` code.  The comments in the code
should hopefully provide a good explanation of what's going on.  Rather than repeat those comments here,
we'll provide a bit more commentary on the non-obvious bits.

### Malformed requests

One of Barrister's selling points is that it helps ensure that requests and responses match the types
defined in the IDL so that you don't have to manually deal with that validation in your application.

You can see an example of this in action near the bottom of `contact_client.py`

    try:
        bad = { "first" : "Sam", "last" : "Jones", "email" : "foo@bar.com" }
        client.ContactService.put(bad)
        print "What? The server let us send it a bad contact.. Bug report!"
    except barrister.RpcException as e:
        # this crazy number comes from the JSON-RPC 2.0 spec, which 
        # we are basing our message formats off of:
        # http://jsonrpc.org/specification
        # -32602 == invalid method parameters
        assert(e.code == -32602)
        print "Nope, wouldn't allow it. e.msg: %s" % e.msg

`e.msg` contains the error message generated by the server.  In this case, the Barrister runtime created
this message.

### Error handling

The `ContactService` class is a plain Python class.  It doesn't inherit from anything or have any 
decorators.  The only area where Barrister appears is in the error handling code.  Barrister errors 
contain an integer error code, and a string message.  Optionally you can include a 3rd parameter that 
provides additional information to the client about the error.  

The `put()` method raises an error if the user has more than 10 contacts:

    def put(self, contact):
        contactId = self._get_or_create_id(contact, "contactId")
        if not self.contacts.has_key(contactId):
            userId = contact["userId"]
            if len(self.getAll(userId)) >= 10:
                msg = "User %s is at the 10 contact limit" % userId
                raise barrister.RpcException(ERR_LIMIT, msg)
        self.contacts[contactId] = contact
        return contactId
        
If this error is raised, the runtime automatically traps it and marshals the error code and message.
The error will be re-thrown on the client side.  See this client code:

    try:
        email = "deny_me@example.com"
        contact = new_contact(bobId, rand_val(first_names), rand_val(last_names), email)
        client.ContactService.put(contact)
        print "Darn! Bob is over the limit, but server let him add another anyway!"
        sys.exit(1)
    except barrister.RpcException as e:
        # prove that we got the correct error code
        assert(e.code == 102)
        print "Sorry Bob, you have too many contacts!"

In this case we expect the `put()` call to fail with a RpcException

### Batch Requests

Barrister allows you to batch multiple requests in a single call, which can speed things up if your
requests are small and the HTTP/network overhead becomes noticeable.

The example from the client is here:

    maryContactIds = []
    batch = client.start_batch()
    for i in range(5):
        email = "email-%s-%d@example.com" % (maryId, i)
        contact = new_contact(maryId, rand_val(first_names), rand_val(last_names), email)
        # Note: nothing is returned at this point
        batch.ContactService.put(contact)
    
    result = batch.send()
    for i in range(result.count):
        # each result is unmarshaled here, and a RpcException would be thrown
        # if that particular result in the batch failed
        maryContactIds.append(result.get(i))

A few items of note:

* `client.start_batch()` creates the `barrister.Batch` object
* You can make calls against the `batch` object as if it were the client.  
  It has the same proxy interface classes hung off it.
* **But** none of the calls you make will return anything, since we haven't sent the request yet
* `batch.send()` makes the call to the server and returns a `barrister.BatchResult`
* You have to call `result.get(offset)` to fetch each result
  * If the individual result contains an error, a `RpcException` will be thrown on that `get()` call
  * That allows you to trap each error individually if desired
* The order of elements in the `result` object will match the order of your requests

## More information

### IDL Syntax

The [main Barrister docs](http://barrister.bitmechanic.com/docs.html) explain how to write an IDL file and
run the `barrister` tool to convert it to a `json` file.

### Python API

The API reference based on our latest Jenkins build is available here:

http://barrister.bitmechanic.com/api/python/latest/


