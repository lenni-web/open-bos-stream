const encoderFields = [

    {

        property: "bitrate",
        row: "cfg-row-bitrate",
        input: "cfg-bitrate",

    },

    {

        property: "pixel_format",
        row: "cfg-row-pixel-format",
        input: "cfg-pixel-format",

    },

    {

        property: "preset",
        row: "cfg-row-preset",
        input: "cfg-preset",

    },

    {

        property: "tune",
        row: "cfg-row-tune",
        input: "cfg-tune",

    },

];

function loadEncoderConfig() {

    const select =

        document.getElementById(
            "cfg-encoder-codec"
        );

    if (!select) {
        return;
    }

    if (

        currentConfig.encoder.codec

    ) {

        select.value =
            currentConfig.encoder.codec;

    }

    else if (

        select.options.length > 0

    ) {

        select.selectedIndex = 0;

        currentConfig.encoder.codec =
            select.value;

    }

    const encoder =

        availableEncoders.find(

            e => e.codec ===
                currentConfig.encoder.codec

        );

    if (!encoder) {
        return;
    }

    renderEncoderOptions(
        encoder,
        currentConfig.encoder,
    );

    updateEncoderOptions();

    select.onchange =
        onEncoderChanged;

}

function saveEncoderConfig() {

    const codec =
        document.getElementById(
            "cfg-encoder-codec"
        )?.value;

    if (!codec) {
        return;
    }

    currentConfig.encoder.codec =
        codec;

    const encoder =

        availableEncoders.find(

            e => e.codec === codec

        );

    if (!encoder) {
        return;
    }

    encoder.options.forEach(

        option => {

            const input =

                document.getElementById(
                    `cfg-${option.id}`
                );

            if (!input) {
                return;
            }

            currentConfig.encoder[
                option.id
            ] = input.value;

        }

    );

}

function applyDefault(id, value) {

    const field =
        document.getElementById(id);

    if (!field) {
        return;
    }

    if (field.value === "") {

        field.value = value;

    }

}

function updateEncoderOptions() {

    const codec =

        document.getElementById(
            "cfg-encoder-codec"
        ).value;

    const encoder =

        availableEncoders.find(

            e => e.codec === codec

        );

    if (!encoder) {
        return;
    }

    renderEncoderOptions(

        encoder,

        currentConfig.encoder,

    );

}

function onEncoderChanged() {

    const codec =

        document.getElementById(
            "cfg-encoder-codec"
        ).value;

    const encoder =

        availableEncoders.find(

            e => e.codec === codec

        );

    if (!encoder) {
        return;
    }

    renderEncoderOptions(
        encoder
    );

}

function renderEncoderOptions(
    encoder,
    values = {},
) {

    const container =
        document.getElementById(
            "encoder-options"
        );

    container.innerHTML = "";

    encoder.options.forEach(

        option => {

            const label =
                document.createElement(
                    "label"
                );

            label.htmlFor =
                `cfg-${option.id}`;

            label.textContent =
                option.label;

            container.appendChild(
                label
            );

            let input;

            if (
                option.type === "select"
            ) {

                input =
                    document.createElement(
                        "select"
                    );

                option.choices.forEach(

                    choice => {

                        const opt =
                            document.createElement(
                                "option"
                            );

                        opt.value = choice;

                        opt.textContent =
                            choice;

                        input.appendChild(
                            opt
                        );

                    }

                );

            } else {

                input =
                    document.createElement(
                        "input"
                    );

                input.type =
                    option.type || "text";

            }

            input.id =
                `cfg-${option.id}`;

            input.className =
                "bos-input";

            if (
                option.placeholder
            ) {

                input.placeholder =
                    option.placeholder;

            }

            if (
                option.required
            ) {

                input.required =
                    true;

            }

            const value =
                values[option.id];

            input.value =

                value !== undefined

                    ? value

                    : option.default;

            container.appendChild(
                input
            );

            if (
                option.description
            ) {

                const help =
                    document.createElement(
                        "small"
                    );

                help.className =
                    "bos-help";

                help.textContent =
                    option.description;

                container.appendChild(
                    help
                );

            }

        }

    );

}
