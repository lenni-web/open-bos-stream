let currentConfig = null;

let availableEncoders = [];

async function loadEncoders(
    forceSelection = false,
) {

    if (!currentConfig) {
        return;
    }

    availableEncoders =
        await api.encoders(
            currentConfig.input,
        );

    selectDefaultEncoder(
        forceSelection,
    );

    updateEncoderSelect();

}

async function refreshConfig() {

    try {

        currentConfig =

            await api.config();

        loadInputConfig();

        loadEncoderConfig();

        loadStreamConfig();

        renderStreamOutputs();

    }

    catch (err) {

        console.error(
            "Config:",
            err
        );

    }

}

async function saveConfig() {

    try {

        saveInputConfig();

        saveEncoderConfig();

        saveStreamConfig();

        saveStreamOutputs();

        console.log(
            "CONFIG TO SAVE"
        );

        console.log(
            JSON.stringify(
                currentConfig,
                null,
                2
            )
        );

        await api.saveConfig(
            currentConfig
        );

        await refreshConfig();

        addEvent(
            "success",
            "⚙️ Konfiguration gespeichert"
        );

    }

    catch (err) {

        console.error(
            "Config:",
            err
        );

        addEvent(
            "error",
            "⚙️ Konfiguration konnte nicht gespeichert werden"
        );

    }

}

function updateEncoderSelect() {

    const select =

        document.getElementById(
            "cfg-encoder-codec"
        );

    if (!select) {
        return;
    }

    select.innerHTML = "";

    availableEncoders.forEach(

        encoder => {

            const option =

                document.createElement(
                    "option"
                );

            option.value =
                encoder.codec;

            option.textContent =
                encoder.name;

            option.disabled =
                !encoder.available;

            select.appendChild(
                option
            );

        }

    );

}

function findEncoder(codec) {

    return availableEncoders.find(

        encoder =>

            encoder.codec === codec &&

            encoder.available

    );

}

function preferredEncoders(
    inputType,
) {

    switch (inputType) {

        case "rtmp":
        case "rtsp":
        case "srt":

            return [
                "copy",
                "libx264",
                "h264_v4l2m2m",
                "libx265",
            ];

        default:

            return [
                "h264_v4l2m2m",
                "libx264",
                "libx265",
                "copy",
            ];
    }

}

function selectDefaultEncoder(
    force = false,
) {

    //
    // Benutzerwahl beibehalten,
    // solange der Encoder noch verfügbar ist.
    //
    if (

        !force &&

        currentConfig.encoder.codec &&

        findEncoder(
            currentConfig.encoder.codec
        )

    ) {

        return;

    }

    const preferred =
        preferredEncoders(
            currentConfig.input.type,
        );

    for (const codec of preferred) {

        const encoder =
            findEncoder(codec);

        if (encoder) {

            currentConfig.encoder.codec =
                encoder.codec;

            return;

        }

    }

    if (availableEncoders.length > 0) {

        currentConfig.encoder.codec =
            availableEncoders[0].codec;

    }

}
