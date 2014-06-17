function create_input(container, descr, type) {
    var name = descr['name'];
    var e = '<div id="' + name + '" class="control-group">';
    e += '<label for="input_' + name + '">' + name + '</label>';
    e += '<div class="controls">';
    e += '<input id="input_' + name + '" name="' + name + '" type="' + type + '"></input>';
    if ('description' in descr) {
        e += '<p class="help-block">' + descr['description'] + '</p>';
    }
    e += '</div>';
    e += '</div>';

    container.append(e);
}

function set_input(container, descr, value) {
    var name = descr['name'];
    container.find("> #" + name + " #input_" + name).val(value);
}

function get_input(container, descr) {
    var name = descr['name'];
    return container.find("> #" + name + " #input_" + name).val();
}

function create_str(container, descr) {
    return create_input(container, descr, 'text');
}

function create_password(container, descr) {
    return create_input(container, descr, 'password');  
}

function create_int(container, descr) {
    return create_input(container, descr, 'number');    
}

function set_bool(container, descr, value) {
    var name = descr['name'];
    container.find("> #" + name + " #input_" + name).prop('checked', value);
}

function get_bool(container, descr, value) {
    var name = descr['name'];
    return container.find("> #" + name + " #input_" + name).prop('checked');
}

function create_bool(container, descr) {
    return create_input(container, descr, 'checkbox');  
}

function create_enum(container, descr) {
    var name = descr['name'];
    var e = '<div id="' +  name + '" class="control-group">';
    e += '<label for="input_' + name + '">' + name + '</label>';
    e += '<div class="controls">';
    e += '<select id="input_' + name + '" name="' + name + '">';
    for (var i = 0 ; i < descr['choices'].length ; i++) {
        var val = descr['choices'][i];
        e += '<option value="' + val + '">' + val + '</option>'
    }
    e += '</select>';
    if ('description' in descr) {
        e += '<p class="help-block">' + descr['description'] + '</p>';
    }
    e += '</div>';
    e += '</div>';

    container.append(e);
}

function create_section(container, descr) {
    var name = descr['name'];
    
    var e = '<div id="' + name + '" class="control-group"><h3>' + name + '</h3></div>';
    container.append(e);

    var sub_container = container.find("#" + name);

    if (!descr['repeat']) {
        create_config(sub_container, descr['content']);
    } else {
        sub_container.append('<a id="add_' + name + '" href="#">Add</a>');
        var num = descr['min'] || 0;
        for (var i = 0 ; i < num ; i++) {
            sub_container.append('<div class="sub_section"></div>');
            var sub_section = sub_container.find(".sub_section").last();
            create_config(sub_section, descr['content']);
        }

        container.on('click', 'a#add_' + name, function(e) {
            e.preventDefault();
            sub_container.append('<div class="sub_section"></div>');
            var sub_section = sub_container.find(".sub_section").last();
            create_config(sub_section, descr['content']);
            sub_section.append('<a id="remove_' + name + '" href="#">Remove</a>');
        });

        container.on('click', 'a#remove_' + name, function(e) {
            e.preventDefault();
            $(this).parent().remove();
        });
    }
}

function set_section(container, descr, value) {
    if (!descr['repeat']) {
        set_config(container, descr['content'], value);
    } else {
        var sub_container = container.find("#" + descr['name']);
        sub_container.find(".sub_section").remove();
        
        var min = descr['min'] || 0;

        for (var i = 0 ; i < value.length ; i++) {
            sub_container.append('<div class="sub_section"></div>');
            var sub_section = sub_container.find(".sub_section").last();
            create_config(sub_section, descr['content']);
            set_config(sub_section, descr['content'], value[i]);
            if (i >= min) {
                sub_section.append('<a id="remove_' + descr['name'] + '" href="#">Remove</a>');
            }
        }
    }
}

function get_section(container, descr) {
    if (!descr['repeat']) {
        return get_config(container, descr['content']);
    } else {
        var ret = [];
        var sub_sections = container.find("#" + descr['name'] + " .sub_section");
        $.each(sub_sections, function() {
            ret.push(get_config($(this), descr['content']));
        });
        return ret;
    }
}

function create_nested_enum(container, descr) {
    var name = descr['name'];
    
    var e = '<div id="' + name + '" class="control-group">';
    e += '<label for="input_' + name + '">' + name + '</label>';
    e += '<div class="controls">';
    e += '<select id="input_' + name + '" name="' + name + '">';
    for (var i = 0 ; i < descr['choices'].length ; i++) {
        var val = descr['choices'][i]['value'];
        e += '<option value="' + i + '">' + val + '</option>'
    }
    e += '</select>';
    if ('description' in descr) {
        e += '<p class="help-block">' + descr['description'] + '</p>';
    }
    e += '</div>';
    e += '</div>';

    container.append(e);

    var sub_container = container.find("#" + name);

    for (var i = 0 ; i < descr['choices'].length ; i++) {
        sub_container.append('<div id="c' + i + '" class="sub_section"></div>');
        var sub_section = sub_container.find(".sub_section").last();
        create_config(sub_section, descr['choices'][i]['content']);
    }

    sub_container.find(".sub_section").hide();
    sub_container.find("#c0").show();

    sub_container.find("#input_" + name).change(function(e) {
        sub_container.find(".sub_section").hide();
        sub_container.find("#c" + $(this).val()).show();
    });
}

function set_nested_enum(container, descr, value) {
    var choice = value[0];
    var config = value[1];

    var choice_index = 0
    for (var i = 0 ; i < descr['choices'].length ; i++){
        if (descr['choices'][i]['value'] == choice) {
            choice_index = i;
        }
    }

    container.find("#input_" + descr['name']).val(choice_index).change();
    var sub_section = container.find(".sub_section#c" + choice_index);
    set_config(sub_section, descr['choices'][choice_index]['content'], config);
}

function get_nested_enum(container, descr) {
    var i = container.find("#input_" + descr['name']).val();
    var elem = descr['choices'][i];

    return [ elem['value'], get_config(
                                container.find(".sub_section#c" + i),
                                elem['content']) ];
}

/**
 * Set the configuration values in the form.
 */
function set_config(container, description, config) {
    $.each(description, function(index, item) {
        var type  = item['type'];
        var name = item['name'];

        if (name in config) {
            if (type == 'str' ||  type == 'password' || type == 'int' || type == 'enum') {
                set_input(container, item, config[name]);
            } else if (type == 'bool') {
                set_bool(container, item, config[name]);
            } else if (type == 'section') {
                set_section(container, item, config[name]);
            } else if (type == 'nested_enum') {
                set_nested_enum(container, item, config[name]);
            } else {
                // Error, ignore field.
            }
        }
    });
}

/**
 * Get the configuration values as a dict from the form.
 */
function get_config(container, description) {
    var config = {};

    $.each(description, function(index, item) {
        var type  = item['type'];
        var name = item['name'];

        if (type == 'str' ||  type == 'password' || type == 'enum') {
            config[name] = get_input(container, item);
        } else if (type == 'int') {
            config[name] = parseInt(get_input(container, item));
        } else if (type == 'bool') {
            config[name] = get_bool(container, item);
        } else if (type == 'section') {
            config[name] = get_section(container, item);
        } else if (type == 'nested_enum') {
            config[name] = get_nested_enum(container, item);
        } else {
            // Error, ignore field.
        }
    });

    return config;
}

function create_config(container, description) {
    $.each(description, function(index, item) {
        var type  = item['type'];

        if (type == 'str') {
            create_str(container, item);
        } else if (type == 'password') {
            create_password(container, item);
        } else if (type == 'int') {
            create_int(container, item);
        } else if (type == 'bool') {
            create_bool(container, item);
        } else if (type == 'enum') {
            create_enum(container, item);
        } else if (type == 'section') {
            create_section(container, item);
        } else if (type == 'nested_enum') {
            create_nested_enum(container, item);
        } else {
            container.append("<div>Unkown configuration type : " + type + "</div>");
        }
    });
}
