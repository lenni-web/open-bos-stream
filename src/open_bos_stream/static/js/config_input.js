let inputTypes = [];

async function loadInputTypes() {

    const response =
        await fetch(
            "/stream/inputs"
        );

    inputTypes =
        await response.json();

    const select =
        document.getElementById(
            "cfg-input-type"
        );

    select.innerHTML = "";

    for (const input of inputTypes) {

        const option =
            document.createElement(
                "option"
            );

        option.value =
            input.type;

        option.textContent =
            input.name;

        select.appendChild(
            option
        );

    }

}

function renderInputFields() {

    const type =
        document.getElementById(
            "cfg-input-type"
        ).value;

    const input =
        inputTypes.find(

            x =>

                x.type === type

        );

    const container =
        document.getElementById(
            "cfg-input-fields"
        );

    container.innerHTML = "";

    if (!input) {

        return;

    }

    for (const field of input.fields) {

        const label =
            document.createElement(
                "label"
            );

        label.textContent =
            field.label;

        container.appendChild(
            label
        );

        let element;

        switch (field.widget) {

            case "select":

                element =
                    document.createElement(
                        "select"
                    );

                for (const item of field.options) {

                    const option =
                        document.createElement(
                            "option"
                        );

                    if (

                        typeof item ===
                        "object"

                    ) {

                        option.value =
                            item.value;

                        option.textContent =
                            item.label;

                    }

                    else {

                        option.value =
                            item;

                        option.textContent =
                            item;

                    }

                    element.appendChild(
                        option
                    );

                }

                break;

            case "number":

                element =
                    document.createElement(
                        "input"
                    );

                element.type =
                    "number";

                break;

            case "password":

                element =
                    document.createElement(
                        "input"
                    );

                element.type =
                    "password";

                break;

            case "checkbox":

                element =
                    document.createElement(
                        "input"
                    );

                element.type =
                    "checkbox";

                break;

            default:

                element =
                    document.createElement(
                        "input"
                    );

                element.type =
                    "text";

        }

        element.className =
            "bos-input";

        element.id =
            "cfg-" + field.name;

        if (

            field.widget ===
            "checkbox"

        ) {

            element.checked =

                currentConfig.input[
                    field.name
                ] ??

                field.default ??

                false;

        }

        else {

            element.value =

                currentConfig.input[
                    field.name
                ] ??

                field.default ??

                "";

        }

        container.appendChild(
            element
        );

    }

}

async function loadInputConfig() {

    await loadInputTypes();

    const select =
        document.getElementById(
            "cfg-input-type"
        );

    const profileSelect =
        document.getElementById(
            "cfg-source-profile"
        );

    if (profileSelect) {
        profileSelect.value =
            currentConfig.source_profile ??
            "custom";
    }

    if (

        currentConfig.input &&
        currentConfig.input.type

    ) {

        select.value =
            currentConfig.input.type;

    }

    renderInputFields();

}

function saveInputConfig() {

    const profileSelect =
        document.getElementById(
            "cfg-source-profile"
        );

    currentConfig.source_profile =
        profileSelect?.value ??
        "custom";

    currentConfig.input.type =

        document.getElementById(
            "cfg-input-type"
        ).value;

    if (
        currentConfig.source_profile ===
        "capture_card"
    ) {

        currentConfig.input.type =
            "v4l2";

        const streamName =
            currentConfig.stream.name
                .split("/")
                .filter(Boolean)
                .pop() ??
            "drohne";

        currentConfig.input.mode =
            "transcode";

        currentConfig.stream.passthrough =
            false;

        if (
            currentConfig.encoder.codec ===
            "copy"
        ) {
            currentConfig.encoder.codec =
                "h264_v4l2m2m";
        }

        currentConfig.stream.name =
            streamName;

        currentConfig.stream.rtsp_url =
            `rtsp://127.0.0.1:8554/${streamName}`;

        const passthroughCheckbox =
            document.getElementById(
                "cfg-stream-passthrough"
            );

        if (passthroughCheckbox) {
            passthroughCheckbox.checked =
                false;
        }

    } else if (
        currentConfig.source_profile ===
            "rtmp_passthrough"
    ) {

        currentConfig.input.type = "rtmp";
        currentConfig.input.mode = "copy";
        currentConfig.encoder.codec = "copy";
        currentConfig.stream.passthrough = true;
        currentConfig.stream.audio.source = "none";
        currentConfig.stream.audio.device = null;
        currentConfig.stream.overlay.source = "none";

        const streamName =
            currentConfig.stream.name.includes("/")
                ? currentConfig.stream.name
                : `live/${currentConfig.stream.name}`;

        currentConfig.stream.name = streamName;
        currentConfig.input.url =
            `rtmp://127.0.0.1:1935/${streamName}`;
        currentConfig.stream.rtsp_url =
            `rtsp://127.0.0.1:8554/${streamName}`;

    } else if (
        currentConfig.source_profile ===
            "rtmp_repair"
    ) {

        currentConfig.input.type = "rtmp";
        currentConfig.input.mode = "copy_repair";
        currentConfig.encoder.codec = "copy";
        currentConfig.stream.passthrough = false;
        currentConfig.stream.audio.source = "none";
        currentConfig.stream.audio.device = null;
        currentConfig.stream.overlay.source = "none";

        const outputName =
            currentConfig.stream.name
                .split("/")
                .filter(Boolean)
                .pop() ??
            "drohne";

        currentConfig.stream.name = outputName;
        currentConfig.stream.rtsp_url =
            `rtsp://127.0.0.1:8554/${outputName}`;

        const passthroughCheckbox =
            document.getElementById(
                "cfg-stream-passthrough"
            );

        if (passthroughCheckbox) {
            passthroughCheckbox.checked = false;
        }

    }

    const input =

        inputTypes.find(

            x =>

                x.type ===

                currentConfig.input.type

        );

    if (!input) {

        return;

    }

    for (const field of input.fields) {

        const element =

            document.getElementById(

                "cfg-" + field.name

            );

        if (!element) {

            continue;

        }

        switch (field.widget) {

            case "checkbox":

                currentConfig.input[
                    field.name
                ] =
                    element.checked;

                break;

            case "number":

                currentConfig.input[
                    field.name
                ] =

                    element.value === ""

                        ? null

                        : parseInt(
                            element.value,
                            10,
                        );

                break;

            default:

                currentConfig.input[
                    field.name
                ] =
                    element.value;

        }

    }

}

async function refreshAvailableEncoders() {

    //
    // Aktuelle Formulareingaben ins Modell übernehmen
    //
	
    if (!currentConfig) {
        return;
    }

    saveInputConfig();

	await loadEncoders(
	        true,
	    );

    loadEncoderConfig();

}

document.addEventListener(

    "change",

    async event => {

        const target =
            event.target;

        if (

            !target.id ||

            !target.id.startsWith(
                "cfg-"
            )

        ) {

            return;

        }

        //
        // Input-Typ geändert
        //
        if (

            target.id ===
            "cfg-source-profile"

        ) {

            const inputSelect =
                document.getElementById(
                    "cfg-input-type"
                );

            if (target.value === "capture_card") {
                inputSelect.value = "v4l2";
            } else if (
                target.value === "rtmp_passthrough" ||
                target.value === "rtmp_repair"
            ) {
                inputSelect.value = "rtmp";
            }

            saveInputConfig();
            renderInputFields();
            await refreshAvailableEncoders();
            loadStreamConfig();

            return;

        }

        if (

            target.id ===
            "cfg-input-type"

        ) {

            const profileSelect =
                document.getElementById(
                    "cfg-source-profile"
                );

            if (profileSelect) {
                profileSelect.value = "custom";
            }

            currentConfig.source_profile =
                "custom";

            renderInputFields();

            saveInputConfig();

            await refreshAvailableEncoders();

            return;

        }

        //
        // Aktuellen InputBuilder suchen
        //
        const input =

            inputTypes.find(

                x =>

                    x.type ===

                    document.getElementById(

                        "cfg-input-type"

                    ).value

            );

        if (!input) {

            return;

        }

        //
        // Feldname bestimmen
        //
        const field =

            target.id.substring(
                4
            );

        //
        // Änderungen immer übernehmen
        //
        saveInputConfig();

        //
        // Encoder neu bestimmen?
        //
        if (

            input.capability_fields &&

            input.capability_fields.includes(

                field

            )

        ) {

            await refreshAvailableEncoders();

        }

    }

);
