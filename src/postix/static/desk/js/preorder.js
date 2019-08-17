var preorder = {
    /*
     The preorder object delals with everything directly related to redeeming a preorder ticket
     */

    redeem: function (secret) {
        loading.start();
        dialog.reset();
        $.ajax({
            url: '/api/preorderpositions/?secret=' + secret,
            method: 'GET',
            dataType: 'json',
            success: function (data, status, jqXHR) {
                loading.end();
                $("#preorder-input").typeahead('val', "");

                if (data.count !== 1) {
                    if (data.count > 1) {
                        preorder.take_focus();
                        dialog.show_error(gettext('Secret is not unique.'));
                        return;
                    } else {
                        dialog.show_error(gettext('Unknown secret.'));
                        preorder.take_focus();
                        return;
                    }
                }
                var res = data.results[0];
                if (res.is_redeemed) {
                    dialog.show_error(res.redemption_message);
                    preorder.take_focus();
                    return;
                } else if (res.is_canceled) {
                    dialog.show_error(gettext('Ticket has been canceled or is expired.'));
                    preorder.take_focus();
                    return;
                }

                transaction.add_preorder(secret, res.product_name + ' - ' + secret.substring(0, 5) + '...', res.pack_list);
		        preorder.take_focus();
            },
            headers: {
                'Content-Type': 'application/json'
            },
            error: function (jqXHR, status, error) {
                console.log(jqXHR.statusText);
                dialog.show_error(jqXHR.statusText);
                loading.end();
            }
        });
    },

    take_focus: function () {
        window.setTimeout(function () {
            // This is a bit of a hack but it works very well to fix cases
            // where a simple .focus() call won't work because it another event
            // takes focus that is called slightly *after* this event.
            $("#preorder-input").focus().typeahead('val', "");
        }, 100);
    },
    
    _submit: function () {
        var secret = $.trim($("#preorder-input").val());
        if (secret === "") {
            return;
        }
        $("#preorder-input").typeahead("val", "").blur();

        // Special commands
        if (secret.slice(0, 1) === "/") {
            if (commands.process(secret)) {
                preorder.take_focus();
                return;
            }
        }
        preorder.redeem(secret);
    },

    init: function () {
        // Initializations at page load time
        $("#preorder-input").keyup(function (e) {
            if (e.keyCode == 13) { // Enter
                preorder._submit();
            }
        });

        $('body').mouseup(function (e) {
            // Global catch-all "if the finger goes up, we reset the focus"
            if (!$('body').hasClass('has-modal') && !$(e.target).is("input, #btn-checkout")) {
                $("#preorder-input").focus().typeahead("close");
            }
        });

        preorder.take_focus();

        $('#preorder-input').typeahead(null, {
            name: 'preorder-tickets',
            display: 'value',
            minLength: 6,
            source: preorder._typeahead_source
        });
        $('#preorder-input').bind('typeahead:selected', function(obj, datum, name) {
            preorder._submit();
        });
    },

    _typeahead_source: new Bloodhound({
        datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        limit: 4,
        remote: {
            url: '/api/preorderpositions/?search=%QUERY',
            wildcard: '%QUERY',
            transform: function (object) {
                var results = object.results;
                var secrets = [];
                var reslen = results.length;
                for (var i = 0; i < reslen; i++) {
                    secrets.push({
                        value: results[i].secret,
                        count: 1
                    });
                }
                return secrets;
            }
        }
    })
};
