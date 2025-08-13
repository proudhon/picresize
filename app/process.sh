#!/bin/bash
rm ./original/* -f || true
rm ./resized/* -f || true
unzip -q ./originalzip/*.zip -d ./original/
rm ./originalzip/* || true
ZIPFILE=./resizedzip/output-$(date +%Y-%m-%d-%H:%M).zip
convert -size "$1"x"$1" canvas:white "canvas.jpeg"
for image in ./original/*; do
  # Process only files (skip subdirectories if any)
  if [ -f "$image" ]; then
    # Get the filename without path
    filename=$(basename "$image")

    # Get image dimensions (width and height)
    dimensions=$(identify -format "%w %h" "$image")
    width=$(echo $dimensions | cut -d' ' -f1)
    height=$(echo $dimensions | cut -d' ' -f2)

    # Determine the largest side
    if [ "$width" -ge "$height" ]; then
      max_dimension=$width
    else
      max_dimension=$height
    fi

    # Create a temporary file to hold the (possibly resized) image
    tmp_image=$(mktemp --suffix=$(echo "$filename" | sed 's/.*\(\.[^.]\+\)$/\1/'))

    # If the largest side exceeds 1200, resize the image.
    # The geometry "1200x1200>" tells ImageMagick to resize only if
    # the image is larger than these dimensions, maintaining the aspect ratio.
    if [ "$max_dimension" -gt $2 ]; then
      convert "$image" -resize $2x$2\> "$tmp_image"
    else
      # If no resizing is needed, just copy the original image to the temporary file.
      cp "$image" "$tmp_image"
    fi

    # Composite the (resized) image onto the center of the white canvas.
    # The -gravity center option places the image in the center.
    convert canvas.jpeg "$tmp_image" -gravity center -composite "./resized/$filename"

    # Remove the temporary file
    rm "$tmp_image"

    echo "Processed: $filename"
  fi
done
zip -q "$ZIPFILE" ./resized/*
echo "$ZIPFILE"
