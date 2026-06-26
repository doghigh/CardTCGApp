// ============================================================================
//  Lorebox — Scanner Card Catch Tray
//  A 3-wall output jig so trading cards eject, decelerate, and stack neatly
//  in order without flipping or pushing earlier cards out.
//
//  HOW IT WORKS
//    - Side rails keep cards square as they land.
//    - A sloped floor lets each card slide forward and settle flat.
//    - A back wall stops the card (line it with felt/foam to kill bounce).
//    - A low hold-down lip at the mouth stops cards riding up and flipping.
//
//  PRINTING
//    - Orient as modeled (floor down). The hold-down lip is the only overhang;
//      it's short, so most slicers bridge it fine. If yours sags, enable
//      supports just for the lip, or set lip_overhang = 0 to omit it and add a
//      strip of tape/acrylic by hand later.
//    - PLA/PETG, 3 perimeters, 15-20% infill is plenty — this carries no load.
//    - Sand or file the inside floor smooth, or line it with felt; you want
//      cards to slide, not catch.
//
//  TUNING (do this with a foam-board mock first, then transfer numbers here)
//    - Cards bounce back / flip   -> add foam to back wall, or raise back_clear
//    - Cards ride up at the mouth -> lower lip_gap toward 4 mm
//    - Bottom card gets shoved    -> add felt to floor (grip), or raise slope
//    - Cards jam at the mouth     -> raise lip_gap, or pull tray back from slot
// ============================================================================

// ----------------------------------------------------------------------------
//  PRESET — Epson DS-575W (straight path, cards fed LONG-EDGE-FIRST)
//  Epson's guidance for thick media: push the output tray extension IN and let
//  cards eject freely onto the surface below. So this tray sits free on the
//  desk, mouth butted to the scanner front, at desk level (no riser, no hook).
//  Feeding long-edge-first means the LONG edge spans the mouth and the card
//  travels its SHORT dimension — hence the swapped card_w / card_l below.
//  Put rubber feet / Dycem under the tray so eject recoil doesn't push it away.
//
//  If you instead feed SHORT-edge-first, use card_w = 63.5; card_l = 88.9;
// ----------------------------------------------------------------------------

/* [Card size] */
card_w      = 88.9;   // DS-575W long-edge-first: long edge spans the mouth
card_l      = 63.5;   // ...card travels its short dimension. Sleeved? +2-3 mm.

/* [Fit clearances] */
side_clear  = 2.0;    // gap each side of the card (rails)
back_clear  = 12.0;   // extra length past the card before the back wall
                      //   = how far cards travel after fully ejecting

/* [Structure] */
wall        = 2.4;    // wall thickness
floor_th    = 2.4;    // floor thickness (at the thin/front edge)
wall_h      = 26.0;   // side-wall height (hold a tall-ish stack)
back_h      = 30.0;   // back-wall height (a touch taller than the sides)

/* [Slope] */
slope_deg   = 7.0;    // floor tilt downhill, away from the scanner
                      //   higher = cards settle harder against the back wall

/* [Hold-down lip — the anti-flip feature] */
lip_gap     = 5.0;    // clear height under the lip at the mouth
                      //   (cards slide UNDER this; keep it low, ~4-6 mm)
lip_overhang= 12.0;   // how far the lip reaches in over the floor
                      //   keep <= ~1/3 of card_l (set to 0 to omit entirely)
lip_th      = 2.4;    // lip thickness

/* [Optional riser feet — lift the mouth to meet the scanner output] */
// Measure how high the scanner's output slot sits above the desk, subtract the
// tray's own mouth height, and put the difference here. Leave 0 if the tray
// already lines up (e.g. it tucks under the scanner's lip).
riser_h     = 0.0;
riser_w     = 14.0;   // footprint of each foot

/* [Quality] */
$fn = 48;

// ---- Derived -------------------------------------------------------------
inner_w  = card_w + 2*side_clear;          // clear width between rails
inner_l  = card_l + back_clear;            // floor run, mouth -> back wall
outer_w  = inner_w + 2*wall;
outer_l  = inner_l + wall;                 // back wall only (mouth is open)
slope_rise = inner_l * tan(slope_deg);     // back edge sits this much higher

// ==========================================================================
module tray() {
    difference() {
        union() {
            // ---- Sloped floor (a wedge: thin at the mouth, thick at back) --
            // Built as a prism so the top face tilts up toward the back wall.
            hull() {
                // front (mouth) edge — thin
                translate([0, 0, 0])
                    cube([outer_w, wall*0.001 + 0.01, floor_th]);
                // back edge — raised by the slope
                translate([0, outer_l - 0.01, slope_rise])
                    cube([outer_w, 0.01, floor_th]);
            }

            // ---- Side rails (follow the sloped floor) ----------------------
            for (x = [0, outer_w - wall])
                translate([x, 0, 0])
                    side_wall();

            // ---- Back wall -------------------------------------------------
            translate([0, outer_l - wall, 0])
                cube([outer_w, wall, slope_rise + floor_th + back_h]);

            // ---- Hold-down lip at the mouth --------------------------------
            if (lip_overhang > 0) {
                translate([wall, 0, floor_th + lip_gap])
                    cube([inner_w, lip_overhang, lip_th]);
                // little posts connecting lip to the floor at the very corners
                for (x = [wall, outer_w - wall - 0.01])
                    translate([x - (x>wall?wall:0), 0, floor_th])
                        cube([wall, wall, lip_gap + lip_th]);
            }

            // ---- Optional riser feet under the mouth -----------------------
            if (riser_h > 0)
                for (x = [0, outer_w - riser_w])
                    translate([x, 0, -riser_h])
                        cube([riser_w, riser_w, riser_h]);
        }
    }
}

module side_wall() {
    // A wall whose bottom follows the sloped floor and whose top is level-ish.
    hull() {
        cube([wall, 0.01, floor_th + wall_h]);                       // front
        translate([0, outer_l - 0.01, 0])
            cube([wall, 0.01, slope_rise + floor_th + wall_h]);      // back
    }
}

tray();

// --- Quick reference printed to the console on render ---
echo(str("Outer footprint: ", outer_w, " x ", outer_l, " mm"));
echo(str("Back wall total height: ", slope_rise + floor_th + back_h, " mm"));
echo(str("Slope rise over run: ", slope_rise, " mm"));
