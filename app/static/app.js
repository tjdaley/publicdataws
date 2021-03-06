'use strict';

var controller = {
    deleteObjectionTemplate: function(id)
    {
        let payload = {
            id: id,
        };

        $.ajax(
            {
                method: 'POST',
                url: '/objection/template/delete',
                data: payload
            }
        )
        .done(function(msg)
        {
            if (msg.success == false)
                console.log(msg);
        });
    },

    getObjectionOptions: function(discovery_type, callback)
    {
        var payload = {
            type: discovery_type
        }

        $.ajax(
            {
                method: 'POST',
                url: '/objection/list',
                data: payload
            }
        )
        .done(function(msg)
        {
            if (msg.success == false)
                console.log(msg);
            else
                callback(msg.objections);
        });
    },

    getObjectionText: function(objection_labels, request_number, callback)
    {
        if (objection_labels.length == 0)
        {
            return {'success': true, 'message': 'No objections selected.', objections: {}};
        }

        var payload = {
            objections : objection_labels
        }

        $.ajax(
            {
                method: 'POST',
                url: '/objection/text',
                data: payload
            }
        )
        .done(function(msg)
        {
            if (msg.success == false)
                console.log(msg);
            else
                callback(request_number, msg.objections);
        });
    },

    deleteResponseTemplate: function (id) {
        let payload = {
            id: id,
        };

        $.ajax(
            {
                method: 'POST',
                url: '/response/template/delete',
                data: payload
            }
        )
            .done(function (msg) {
                if (msg.success == false)
                    console.log(msg);
            });
    },

    getResponseOptions: function (discovery_type, callback) {
        var payload = {
            type: discovery_type
        }

        $.ajax(
            {
                method: 'POST',
                url: '/response/list',
                data: payload
            }
        )
            .done(function (msg) {
                if (msg.success == false)
                    console.log(msg);
                else
                    callback(msg.objections);
            });
    },

    getResponseText: function (response_labels, request_number, callback) {
        if (response_labels.length == 0) {
            return { 'success': true, 'message': 'No responses selected.', objections: {} };
        }

        var payload = {
            objections: response_labels
        }

        $.ajax(
            {
                method: 'POST',
                url: '/response/text',
                data: payload
            }
        )
            .done(function (msg) {
                if (msg.success == false)
                    console.log(msg);
                else
                    callback(request_number, msg.responses);
            });
    },

    lookupAttorney: function(bar_number, callback)
    {
        if (bar_number.length == 0) return;

        $.ajax(
            {
                method: 'POST',
                url: '/attorney/find/'+bar_number
            }
        )
        .done(function(msg)
        {
            if (msg.success == false)
                console.log(msg);
            else
                callback(msg);
        });
    },

    saveDiscoveryRequestText: function(id, request_number, request_text, response_text)
    {
        let payload = {
            id: id,
            request_number: request_number,
            request_text: request_text,
            response_text: response_text
        };

        $.ajax(
            {
                method: 'POST',
                url: '/discovery/request/save',
                data: payload
            }
        )
        .done(function(msg)
        {
            if (msg.success == false)
                console.log(msg);
        });
    },

    deleteDiscoveryRequest: function(id, request_number)
    {
        let payload = {
            id: id,
            request_number: request_number
        };

        $.ajax(
            {
                method: 'POST',
                url: '/discovery/request/delete',
                data: payload
            }
        )
        .done(function(msg)
        {
            if (msg.success == false)
                console.log(msg);
        });
    },

    deleteDiscoveryDocument: function(id)
    {
        let payload = {'id': id}
        $.ajax({method: 'POST', url: '/discovery/document/delete', data: payload})
        .done(function(msg)
        {
            if (msg.success == false)
                console.log(msg);
        });
    },

    setDiscoveryDocumentCleanedUp: function(id, value)
    {
        let payload = {
            id: id,
            value: value
        };

        $.ajax(
            {
                method: 'POST',
                url: '/discovery/document/set_cleaned_flag',
                data: payload
            }
        )
        .done(function(msg)
        {
            if (msg.success == false)
                console.log(msg);
        });
    },

    setCase:function (event, rivets_binding)
    {
        let button = event.target;
        let id = button.getAttribute("data-id");

        let url;
        let payload;

        if (id == "")
        {
            url = "/clearcaseid/";
            payload = {"_id": "none"};
        }
        else
        {
            url = "/setcaseid/";
            payload = {"_id": id};    
        }

        // Update server-side session cookie
        $.ajax(
            {
                method: "POST",
                url: url,
                data: payload
            })
            .done(function( msg ) 
            {
                console.log(msg);
                if (msg.success)
                {
                    document.location.reload(true);
                }
            });
        },

    showCaseItems: function(event, rivets_binding)
    {
        window.location.assign("/case/items/");
    },

    updateCaseItems: function (event, rivets_binding)
    {
        let button = event.target;
        let db = button.getAttribute("data-db");
        let ed = button.getAttribute("data-ed");
        let rec = button.getAttribute("data-rec");
        let operation = button.getAttribute("data-op")
        let category = button.getAttribute("data-category")
        let description = button.getAttribute("data-description")
        //let case_id = rivets_binding.data.case.id;

        let payload = {
            db: db,
            ed: ed,
            rec: rec,
            //case_id: case_id,
            description: description,
            category: category,
            op: operation,
            key: `PUBLICDATA:${db}.${ed}.${rec}`};
        console.log(payload);
        $.ajax(
        {
            method: "POST",
            url: "/case/update_items/",
            data: payload
        })
        .done(function( msg ) 
        {
            console.log(msg);
            if (msg.success)
            {
                document.location.reload(true);
            }
        });
    },
};

var app = {
    version: "0.0.1",
    views: {},
    data: {
        case: {
            cause_number: sessionStorage.getItem("cause_number"),
            description: sessionStorage.getItem("case_description"),
            id: sessionStorage.getItem("case_id"),
        },
        discovery_request_number: 0,
    },
    controller: controller,
};

app.init = function()
{
    rivets.configure({

        // Attribute prefix in templates
        prefix: 'rv',
      
        // Preload templates with initial data on bind
        preloadData: true,
      
        // Root sightglass interface for keypaths
        rootInterface: '.',
      
        // Template delimiters for text bindings
        templateDelimiters: ['{', '}'],
      
        // Alias for index in rv-each binder
        iterationAlias : function(modelName) {
          return '%' + modelName + '%';
        },
      
        // Augment the event handler of the on-* binder
        // We can add any code we want in here.
        handler: function(target, event, binding) 
        {
            this.call(target, event, binding.view.models)
        },
      
        // Since rivets 0.9 functions are not automatically executed in expressions. If you need backward compatibilty, set this parameter to true
        executeFunctions: false
      
    });
}

/**
 * Bind initial views.
 * 
 * Binds initial views to the app's data model.
 * 
 * @since 0.0.1
 */
app.onReady = function()
{
    app.init();
    app.bind("#app", {data: app.data, controller: app.controller,});
    app.bind("#case_information", {data: app.data, controller: app.controller,});
}

/**
 * Binds an object to a DOM element for two-way updates.
 * 
 * Binds an object to a DOM element for two-way updates. Creates a fully bound view. Saves
 * a reference to the fully-bound view in app.bindings, indexed by the given CSS selector.
 * The saved view can be ubound through a call to app.unbind(css_selector) using the
 * exact same CSS selector.
 * 
 * @since 0.0.1
 * 
 * @param string css_selector CSS selector of element to be found to *bound_item*.
 * @param object bound_item   Object to bind into the newly created view.
 */
app.bind = function(css_selector, bound_item)
{
    let element = $(css_selector)[0];
    let view = rivets.bind(element, bound_item);
    app.views[css_selector] = view;
}

/**
 * Unbinds a view.
 * 
 * Unbinds a Rivets.js view using the provided CSS selector as an index into our dictionary
 * of saved views.
 * 
 * @since 0.0.1
 * 
 * @param string css_selector CSS selector used in the original call to app.bind().
 */
app.unbind = function(css_selector)
{
    let view = app.views[css_selector];
    if (view)
    {
        view.unbind();
    }
}