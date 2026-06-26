// ============================================================================
//  Lorebox — Elevated-Scanner Gravity Slide + Catch Bin  (Epson DS-575W)
//
//  For when the scanner is raised on a stand. Cards eject from the elevated
//  output slot, drop onto an inclined slide, and glide down into a stack
//  against a backstop — gravity decelerates them so they land flat and in
//  order instead of shooting across the desk and flipping.
//
//  PLACEMENT
//    - This part sits on the desk in FRONT of the scanner.
//    - Its high back edge reaches UP to just below the output slot.
//    - Set `drop_height` = how high the output slot sits above the desk
//      (= your stand lift + the slot's height above the scanner's own base).
//      Aim the slot so cards land on the slide a bit below its top edge.
//
//  THE STAND (build in wood/printed blocks/brackets — not modeled here)
//    - Just needs to hold the DS-575W level and stable at your chosen height.
//    - 80-130 mm of lift gives a nice slide without a huge footprint.
//    - Leave the front clear so cards fall straight onto the slide.
//    - Remember Epson's tip: push the scanner's output extension IN so cards
//      eject freely (straight path) rather than curling onto its own tray.
//
//  PRINTING
//    - Big footprint; print in halves along the width and glue/dovetail if it
//      exceeds your bed (split_print below cuts it in two mirrored halves).
//    - The slide surface should be SMOOTH: print that face up, or sand it, or
//      lay down packing tape / adhesive PTFE so cards glide.
//    - Line the backstop face with felt/foam to kill the last bit of bounce.
//    - PLA/PETG, 3 perimeters, 10-15% infill (carries no real load).
//
//  TUNING (mock in foam board first!)
//    - Cards stall on the slide      -> raise ramp_angle, or smooth the slide
//    - Cards arrive too fast / flip  -> lower ramp_angle toward 28
//    - Cards overshoot the backstop  -> raise backstop_h
//    - Cards don't land on the slide -> raise/lower the stand so the slot
//                                       aims onto the upper third of the slide
// ============================================================================

/* [Card] — DS-575W feeds long-edge-first, so the long edge spans the slide */
card_w     = 88.9;    // width across the slide (sleeved? add 2-3 mm)
side_clear = 4.0;     // gap each side of the card (rails) — bumped from 2.5
                      //   after real-world testing showed it ran a touch tight

/* [Geometry] */
drop_height = 100;    // output-slot height above the desk (= stand lift, ~)
ramp_angle  = 33;     // slide tilt from horizontal (28-36 is the sweet spot)
rail_h      = 15;     // rail height above the slide surface
backstop_h  = 24;     // front wall the stack leans against
backstop_th = 3.2;    // backstop thickness

/* [Structure] */
wall        = 2.8;    // side-rail thickness

/* [Funnel guide] — splayed wings at the top that steer off-center cards in */
flare       = true;   // false = plain rails, no funnel
flare_len   = 45;     // how far down the slide the wings reach (along depth)
flare_h     = 32;     // how tall the wings rise above the slide at the back
flare_angle = 30;     // outward splay from vertical (bigger = wider mouth)

/* [Printing] */
split_print = false;  // true = output two mirrored half-width pieces to glue
$fn = 56;

// ---- Derived -------------------------------------------------------------
inner_w = card_w + 2*side_clear;        // clear channel width
outer_w = inner_w + 2*wall;
L       = drop_height / tan(ramp_angle); // slide horizontal run (depth)

function slideZ(x) = x / L * drop_height; // slide surface height at depth x

module side_profile() {
    // x = depth (0 = front/backstop, L = back/high), y = height
    polygon([[0, 0], [L, 0], [L, drop_height + rail_h], [0, backstop_h]]);
}

module channel_profile() {
    big = drop_height + rail_h + 30;
    // Everything above the slide surface, from just behind the backstop to the
    // open back. Removing this leaves: solid wedge below, rails, front backstop.
    polygon([[backstop_th, slideZ(backstop_th)],
             [L + 1,       drop_height],
             [L + 1,       big],
             [backstop_th, big]]);
}

module wing() {
    // local: x = along depth, y = up, z = thickness. Low at the front of the
    // flare zone, full height at the back, so it blends into the rail.
    linear_extrude(height = wall)
        polygon([[0, 0], [flare_len, 0], [flare_len, flare_h], [0, flare_h * 0.25]]);
}

module wings() {
    // Left wing: rises from the back of the left rail, splayed outward (-z).
    translate([L - flare_len, drop_height, wall])
        rotate([-flare_angle, 0, 0]) wing();
    // Right wing: mirror of the left across the width centerline.
    translate([0, 0, outer_w]) mirror([0, 0, 1])
        translate([L - flare_len, drop_height, wall])
            rotate([-flare_angle, 0, 0]) wing();
}

module part() {
    union() {
        difference() {
            linear_extrude(height = outer_w) side_profile();
            translate([0, 0, wall])
                linear_extrude(height = inner_w) channel_profile();
        }
        if (flare) wings();
    }
}

// Stand height up so +Z is "up" when viewed.
module assembly() {
    if (split_print) {
        // two halves split along the width centerline, laid side by side.
        H = drop_height + flare_h + rail_h + 10;   // generous: clears wings
        rotate([90, 0, 0]) intersection() {
            part();
            translate([-5, -5, -flare_h]) cube([L + 10, H, outer_w/2 + flare_h]);
        }
        translate([0, outer_w/2 + 12, 0])
            rotate([90, 0, 0]) intersection() {
                part();
                translate([-5, -5, outer_w/2]) cube([L + 10, H, outer_w/2 + flare_h]);
            }
    } else {
        rotate([90, 0, 0]) part();
    }
}

assembly();

echo(str("Footprint: depth ", L, " mm  x  width ", outer_w, " mm"));
echo(str("Back (tall) edge height: ", drop_height + rail_h, " mm"));
echo(str("Set drop_height to your slot-above-desk height; current = ", drop_height));
